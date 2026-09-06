"""Qt desktop shell for Windows; Linux GTK entry point remains independent."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import replace
import sys
import threading

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea,
    QSlider, QSystemTrayIcon, QVBoxLayout, QWidget)

from .history import SessionHistory
from .windows_audio import WindowsRouter, endpoints, topology
from .windows_probe import PHRASE, ProbeError, winrt_voices
from .windows_runtime import (WindowsConfig, WindowsSpeechQueue, com_apartment,
    discover_windows_models, parse_hotkey, voice_dir)

STYLE = """
QWidget { background: #121c1b; color: #e0e8e3; font: 14px 'Segoe UI'; }
QLabel#brand { color: #80d2c6; font-size: 24px; font-weight: 700; }
QLabel#muted { color: #a9bab2; }
QLabel#error { color: #f28b70; }
QLineEdit, QComboBox, QDoubleSpinBox { background: #101918; border: 1px solid #465653;
    border-radius: 7px; padding: 8px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #80d2c6; }
QPushButton { background: #243330; border: 1px solid #465653; border-radius: 7px; padding: 8px 12px; }
QPushButton:hover { border-color: #80d2c6; }
QPushButton:disabled, QComboBox:disabled, QCheckBox:disabled { color: #647773; }
QSlider::groove:horizontal { height: 6px; background: #243330; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; margin: -5px 0; background: #80d2c6; border-radius: 8px; }
QMenu { border: 1px solid #465653; }
QMenu::item { padding: 8px 22px; }
QMenu::item:selected { background: #243330; }
"""


def icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#121c1b"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#80d2c6"))
    font = painter.font()
    font.setPixelSize(44)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "C")
    painter.end()
    return QIcon(pixmap)


class Signals(QObject):
    error = Signal(str)
    status = Signal(str)
    discovered = Signal(object)


class TextEntry(QLineEdit):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setPlaceholderText("Type something to say…")
        self.setMaxLength(5000)
        self.returnPressed.connect(owner.send)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.clear()
            self.owner.hide()
        elif key == Qt.Key.Key_Up:
            self.setText(self.owner.history.previous(self.text()))
        elif key == Qt.Key.Key_Down:
            self.setText(self.owner.history.next())
        else:
            super().keyPressEvent(event)


class Overlay(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.controller = controller
        self.history = SessionHistory(25)
        self.setWindowTitle("Caspr TTS")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        row = QHBoxLayout()
        brand = QLabel("CASPR · TTS")
        brand.setObjectName("brand")
        row.addWidget(brand)
        row.addStretch()
        settings = QPushButton("Settings")
        settings.clicked.connect(controller.show_settings)
        row.addWidget(settings)
        layout.addLayout(row)
        self.voice_label = QLabel()
        self.voice_label.setWordWrap(True)
        self.voice_label.setObjectName("muted")
        layout.addWidget(self.voice_label)
        self.entry = TextEntry(self)
        layout.addWidget(self.entry)
        self.hint = QLabel("Enter send + hide   ·   Esc clear + hide   ·   ↑ ↓ history")
        self.hint.setObjectName("muted")
        layout.addWidget(self.hint)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.resize(560, 220)

    def send(self):
        text = self.entry.text().strip()
        if not text:
            return
        if self.controller.worker:
            self.controller.worker.submit(text, self.controller.config)
        self.history.add(text)
        self.entry.clear()
        self.error.clear()
        self.hide()

    def open(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class Settings(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Caspr TTS · Settings")
        self.resize(660, 720)
        outer = QVBoxLayout(self)
        brand = QLabel("CASPR · SETTINGS")
        brand.setObjectName("brand")
        outer.addWidget(brand)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(14)
        scroll.setWidget(content)
        self.provider = QComboBox()
        self.provider.addItem("Piper · local ONNX model", "piper")
        self.provider.addItem("Microsoft · installed Windows voice", "microsoft")
        form.addRow("Speech provider", self.provider)
        self.microsoft = QComboBox()
        form.addRow("Microsoft voices", self.microsoft)
        self.piper = QComboBox()
        form.addRow("Piper voices", self.piper)
        self.voices_note = QLabel("Choose an installed Microsoft voice, or add a Piper model pair.")
        self.voices_note.setWordWrap(True)
        form.addRow(self.voices_note)
        folder = QPushButton("Open voices folder")
        folder.clicked.connect(self.open_folder)
        form.addRow(folder)
        self.message_output = QComboBox()
        self.preview_output = QComboBox()
        form.addRow("Message output", self.message_output)
        form.addRow("Monitor / preview output", self.preview_output)
        routing = QLabel("Stereo Mix: choose its Realtek playback output for messages; select Stereo Mix in Discord. "
                         "VB-CABLE: messages → CABLE Input; Discord → CABLE Output. Caspr does not change system defaults or Push to Talk.")
        routing.setWordWrap(True)
        form.addRow(routing)
        self.monitor = QCheckBox("Also play messages through monitor output")
        form.addRow(self.monitor)
        self.verified = QCheckBox("I verified preview isolation for this session")
        self.verified.setToolTip("First record your Discord input while playing test audio to the preview output. "
                                 "Confirm that none arrives. Recheck after any mixer or routing change.")
        form.addRow(self.verified)
        note = QLabel("Samples stay disabled until you verify a separate preview output is absent from the capture route. "
                      "Stereo Mix may capture all audio on its output. Windows Listen and external mixers can defeat isolation. "
                      "Verification resets on restart or detected device changes.")
        note.setWordWrap(True)
        form.addRow(note)
        self.sample = QPushButton("Play voice sample to verified preview")
        self.sample.clicked.connect(controller.sample)
        form.addRow(self.sample)
        self.rate = QComboBox()
        for rate in (44100, 48000):
            self.rate.addItem(f"{rate:,} Hz", rate)
        form.addRow("Playback sample rate", self.rate)
        volume_row = QHBoxLayout()
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume_label = QLabel()
        volume_row.addWidget(self.volume)
        volume_row.addWidget(self.volume_label)
        form.addRow("Speech volume", volume_row)
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setSingleStep(0.1)
        self.delay.setSuffix(" seconds")
        form.addRow("Delay from submission", self.delay)
        self.hotkey = QLineEdit()
        form.addRow("Global shortcut", self.hotkey)
        self.hotkey_status = QLabel()
        self.hotkey_status.setWordWrap(True)
        form.addRow(self.hotkey_status)
        self.status = QLabel("Ready")
        form.addRow(self.status)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName("error")
        form.addRow(self.error)
        actions = QHBoxLayout()
        refresh = QPushButton("Refresh voices / outputs")
        refresh.clicked.connect(controller.discover)
        show = QPushButton("Open overlay")
        show.clicked.connect(lambda: controller.overlay.open())
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(QApplication.instance().quit)
        for button in (refresh, show, quit_button):
            actions.addWidget(button)
        outer.addLayout(actions)
        self.provider.currentIndexChanged.connect(lambda: self.change("speech_provider", self.provider.currentData()))
        for combo, key in ((self.microsoft, "microsoft_voice_id"), (self.piper, "model_path"),
                           (self.message_output, "message_endpoint_id"), (self.preview_output, "preview_endpoint_id"),
                           (self.rate, "output_rate")):
            combo.currentIndexChanged.connect(lambda _, c=combo, k=key: self.change(k, c.currentData()))
        self.monitor.toggled.connect(lambda value: self.change("local_monitor", value))
        self.volume.valueChanged.connect(lambda value: self.change("speech_volume", value))
        self.delay.valueChanged.connect(lambda value: self.change("playback_delay_seconds", value))
        self.hotkey.editingFinished.connect(self.set_hotkey)
        self.verified.toggled.connect(controller.verify_preview)

    def change(self, key, value):
        if value is not None:
            self.controller.update(key, value)

    def set_hotkey(self):
        try:
            parse_hotkey(self.hotkey.text())
            self.controller.update("hotkey", self.hotkey.text())
            self.controller.register_hotkey()
        except ProbeError as error:
            self.hotkey_status.setText(str(error))

    def open_folder(self):
        try:
            directory = voice_dir()
            directory.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
        except OSError:
            self.controller.on_error("Could not open the voices folder.")

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class Hotkey(QAbstractNativeEventFilter):
    ID = 0x4341

    def __init__(self, callback, invalidate=lambda: None):
        super().__init__()
        self.callback = callback
        self.invalidate = invalidate
        self.registered = False

    def register(self, shortcut):
        self.close()
        modifiers, key = parse_hotkey(shortcut)
        if sys.platform != "win32":
            return False
        self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.ID, modifiers, key))
        return self.registered

    def close(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, self.ID)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message in (0x0219, 0x0218):  # Device changes and power/suspend/resume
                self.invalidate()
            if msg.message == 0x0312 and msg.wParam == self.ID:
                self.callback()
                return True, 0
        return False, 0


def fill_combo(combo, options, selected, missing="Select…"):
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(missing if not selected else "Saved selection unavailable — choose explicitly", selected)
    for label, value in options:
        combo.addItem(label, value)
    matches = [i for i in range(1, combo.count()) if combo.itemData(i) == selected]
    combo.setCurrentIndex(matches[0] if matches else 0)
    combo.blockSignals(False)


class Controller:
    def __init__(self, app, config=None, start_services=True):
        self.app = app
        self.config = config or WindowsConfig.load()
        self.devices = []
        self.voices = []
        self.verification = None
        self.discovery_busy = False
        self.start_services = start_services
        self.signals = Signals()
        self.worker = None
        self.overlay = Overlay(self)
        self.settings = Settings(self)
        self.signals.error.connect(self.on_error)
        self.signals.status.connect(self.settings.status.setText)
        self.signals.discovered.connect(self.on_discovered)
        self.hotkey = Hotkey(self.overlay.open, self.invalidate_preview)
        self.app.installNativeEventFilter(self.hotkey)
        self.tray = QSystemTrayIcon(icon(), app)
        self.tray.setToolTip("Caspr TTS")
        menu = QMenu()
        menu.addAction("Open overlay", self.overlay.open)
        menu.addAction("Settings", self.show_settings)
        menu.addSeparator()
        menu.addAction("Quit", app.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.overlay.open()
            if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.menu = menu
        self.timer = QTimer()
        self.timer.setInterval(5000)
        self.timer.timeout.connect(lambda: self.discover(voices=False))
        self.sync()
        app.aboutToQuit.connect(self.close)
        if start_services:
            self.worker = WindowsSpeechQueue(self.signals.error.emit, self.signals.status.emit,
                router=WindowsRouter(preview_authorizer=lambda token: token is not None and self.verification is token))
            self.tray.show()
            self.register_hotkey()
            self.discover()
            self.timer.start()

    def update(self, key, value):
        if key in ("message_endpoint_id", "preview_endpoint_id") and getattr(self.config, key) != value:
            self.verification = None
        setattr(self.config, key, value)
        try:
            self.config.save()
        except OSError:
            self.on_error("Settings could not be saved. Check access to your local app data folder.")
        self.sync()

    def sync(self):
        s, c = self.settings, self.config
        for widget, value in ((s.provider, c.speech_provider), (s.rate, c.output_rate)):
            widget.blockSignals(True)
            widget.setCurrentIndex(widget.findData(value))
            widget.blockSignals(False)
        for widget, value, setter in ((s.monitor, c.local_monitor, "setChecked"),
                                      (s.volume, c.speech_volume, "setValue"),
                                      (s.delay, c.playback_delay_seconds, "setValue"),
                                      (s.hotkey, c.hotkey, "setText"),
                                      (s.verified, self.verification is not None, "setChecked")):
            widget.blockSignals(True)
            getattr(widget, setter)(value)
            widget.blockSignals(False)
        s.volume_label.setText(f"{c.speech_volume}%")
        s.microsoft.setEnabled(c.speech_provider == "microsoft")
        s.piper.setEnabled(c.speech_provider == "piper")
        ids = {d.id for d in self.devices}
        can_verify = c.message_endpoint_id in ids and c.preview_endpoint_id in ids and c.message_endpoint_id != c.preview_endpoint_id
        s.verified.setEnabled(can_verify)
        s.sample.setEnabled(can_verify and self.verification is not None)
        voice = s.microsoft.currentText() if c.speech_provider == "microsoft" else s.piper.currentText()
        self.overlay.voice_label.setText(f"{c.speech_provider.title()} · {voice or 'Choose a voice in Settings'}")

    def invalidate_preview(self):
        self.verification = None
        self.sync()

    def verify_preview(self, checked):
        self.verification = (self.config.message_endpoint_id, self.config.preview_endpoint_id, topology(self.devices)) if checked else None
        self.sync()

    def sample(self):
        if self.worker:
            self.worker.submit(PHRASE, self.config, preview=True, preview_verification=self.verification)

    def discover(self, checked=False, *, voices=True):
        if self.discovery_busy or not self.start_services:
            return
        self.discovery_busy = True
        def run():
            result = {}
            try:
                with com_apartment():
                    try:
                        result["devices"] = endpoints()
                    except Exception:
                        result["devices"] = []
                        result["audio_error"] = "Windows outputs could not be enumerated. Refresh after reconnecting the device."
                    if voices:
                        try:
                            result["voices"] = winrt_voices()
                        except Exception:
                            result["voices"] = []
                            result["voice_error"] = "Installed Microsoft voices could not be loaded. Piper remains available."
            except Exception:
                result = {"devices": [], "audio_error": "Windows device discovery could not start."}
            self.signals.discovered.emit(result)
        threading.Thread(target=run, daemon=True, name="Caspr discovery").start()

    def on_discovered(self, result):
        self.discovery_busy = False
        devices = result.get("devices", [])
        if topology(devices) != topology(self.devices):
            self.verification = None
        self.devices = devices
        if "voices" in result:
            self.voices = result["voices"]
        c, s = self.config, self.settings
        fill_combo(s.microsoft, [(f'{v["name"]} · {v["language"]}', v["id"]) for v in self.voices], c.microsoft_voice_id)
        fill_combo(s.piper, [(v.menu_label, v.model_path) for v in discover_windows_models(c.model_path)], c.model_path)
        outputs = [(f"{d.name} · {d.id[-12:]}", d.id) for d in self.devices]
        fill_combo(s.message_output, outputs, c.message_endpoint_id)
        fill_combo(s.preview_output, outputs, c.preview_endpoint_id)
        s.voices_note.setText(result.get("voice_error") or "Microsoft voices are installed by Windows. Piper needs an .onnx and matching .onnx.json in the voices folder; refresh after adding files.")
        if result.get("audio_error"):
            self.on_error(result["audio_error"])
        self.sync()

    def register_hotkey(self):
        try:
            registered = self.hotkey.register(self.config.hotkey)
            self.settings.hotkey_status.setText("Shortcut registered." if registered else
                "Shortcut unavailable or in use. Choose another; the tray still opens Caspr.")
        except ProbeError as error:
            self.settings.hotkey_status.setText(str(error))

    def show_settings(self):
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def on_error(self, message):
        self.settings.error.setText(message)
        self.overlay.error.setText(message)
        if self.start_services:
            self.tray.showMessage("Caspr TTS", message, QSystemTrayIcon.MessageIcon.Warning)

    def close(self):
        self.timer.stop()
        self.hotkey.close()
        self.app.removeNativeEventFilter(self.hotkey)
        self.tray.hide()
        if self.worker:
            self.worker.stop()
