from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .config import AppConfig
from .history import SessionHistory
from .speech import SpeechQueue


APP_ID = "io.github.quickttsmic.App"


class QuickTtsApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.config = AppConfig.load()
        self.history = SessionHistory(self.config.history_limit)
        self.speech = SpeechQueue(lambda: self.config, self._speech_error)
        self.settings_window: Gtk.ApplicationWindow | None = None
        self.overlay_window: Gtk.ApplicationWindow | None = None
        self.entry: Gtk.Entry | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self._load_styles()
        # Startup only runs in the primary GApplication instance. Holding here
        # keeps that background process alive without trapping remote shortcut
        # invocations in their own invisible processes.
        self.hold()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        args = command_line.get_arguments()[1:]
        self.activate()
        if "overlay" in args:
            GLib.idle_add(self.show_overlay)
        else:
            GLib.idle_add(self.show_settings)
        return 0

    def do_activate(self) -> None:
        try:
            self.speech.router.ensure_virtual_mic()
        except Exception as error:
            self._speech_error(str(error))

    def show_overlay(self) -> bool:
        if self.overlay_window is None:
            self.overlay_window = self._build_overlay()
        self.history.reset_navigation(self.entry.get_text() if self.entry else "")
        self.overlay_window.present()
        if self.entry:
            self.entry.grab_focus()
        return GLib.SOURCE_REMOVE

    def show_settings(self) -> bool:
        if self.settings_window is None:
            self.settings_window = self._build_settings()
        self.settings_window.present()
        return GLib.SOURCE_REMOVE

    def _build_overlay(self) -> Gtk.ApplicationWindow:
        window = Gtk.ApplicationWindow(application=self, title="Quick TTS")
        window.set_default_size(680, -1)
        window.set_resizable(False)
        window.set_hide_on_close(True)
        window.add_css_class("overlay-window")

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        shell.add_css_class("overlay-shell")
        shell.set_margin_top(10)
        shell.set_margin_bottom(10)
        shell.set_margin_start(10)
        shell.set_margin_end(10)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        icon.set_pixel_size(18)
        icon.add_css_class("brand-icon")
        heading.append(icon)

        heading_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        eyebrow = Gtk.Label(label="QUICK TTS", xalign=0)
        eyebrow.add_css_class("eyebrow")
        heading_copy.append(eyebrow)
        hint = Gtk.Label(label="Type a message for voice chat", xalign=0)
        hint.add_css_class("hint")
        heading_copy.append(hint)
        heading.append(heading_copy)
        shell.append(heading)

        compose = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.entry = Gtk.Entry(placeholder_text="Type something to say…")
        self.entry.set_hexpand(True)
        self.entry.add_css_class("message-entry")
        self.entry.connect("activate", self._send)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._overlay_key_pressed)
        self.entry.add_controller(key_controller)

        send = Gtk.Button(label="Speak  ↵")
        send.add_css_class("suggested-action")
        send.add_css_class("send-button")
        send.connect("clicked", self._send)

        compose.append(self.entry)
        compose.append(send)
        shell.append(compose)

        footer = Gtk.Label(label="↑↓ history    ·    Esc cancel", xalign=0)
        footer.add_css_class("hint")
        shell.append(footer)
        window.set_child(shell)
        return window

    def _build_settings(self) -> Gtk.ApplicationWindow:
        window = Gtk.ApplicationWindow(application=self, title="Quick TTS Mic — Settings")
        window.set_default_size(680, -1)
        window.set_hide_on_close(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.add_css_class("settings-root")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        header_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        header_icon.set_pixel_size(24)
        header_icon.add_css_class("brand-icon")
        header.append(header_icon)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="Quick TTS Mic", xalign=0)
        title.add_css_class("title")
        heading.append(title)
        subtitle = Gtk.Label(label="A fast, keyboard-first voice for chat", xalign=0)
        subtitle.add_css_class("subtitle")
        heading.append(subtitle)
        heading.set_hexpand(True)
        header.append(heading)

        status = Gtk.Label(label="●  READY")
        status.add_css_class("status-pill")
        status.set_valign(Gtk.Align.CENTER)
        header.append(status)
        outer.append(header)

        voice_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        voice_card.add_css_class("settings-card")
        voice_title = Gtk.Label(label="Voice", xalign=0)
        voice_title.add_css_class("section-title")
        voice_card.append(voice_title)

        model_label = Gtk.Label(label="Piper model", xalign=0)
        model_label.add_css_class("field-label")
        voice_card.append(model_label)

        model_entry = Gtk.Entry(text=self.config.model_path, hexpand=True)
        model_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        model_row.append(model_entry)
        browse = Gtk.Button(label="Browse…")
        browse.connect("clicked", self._browse_model, model_entry)
        model_row.append(browse)
        voice_card.append(model_row)
        model_help = Gtk.Label(
            label="Offline speech · en_GB-alan-medium for this prototype",
            xalign=0,
        )
        model_help.add_css_class("field-help")
        voice_card.append(model_help)
        outer.append(voice_card)

        audio_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        audio_card.add_css_class("settings-card")
        audio_title = Gtk.Label(label="Audio routing", xalign=0)
        audio_title.add_css_class("section-title")
        audio_card.append(audio_title)

        device_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        device_label = Gtk.Label(label="Discord input", xalign=0)
        device_label.add_css_class("field-label")
        device_label.set_hexpand(True)
        device_row.append(device_label)
        device_value = Gtk.Label(label="QuickTTS_Microphone", selectable=True)
        device_value.add_css_class("shortcut-chip")
        device_row.append(device_value)
        audio_card.append(device_row)

        monitor = Gtk.CheckButton(label="Hear speech in headphones")
        monitor.set_active(self.config.local_monitor)
        audio_card.append(monitor)

        output_names = [""]
        output_labels = ["System default"]
        for output in self.speech.router.outputs():
            output_names.append(output.name)
            output_labels.append(output.description)
        output_model = Gtk.StringList.new(output_labels)
        output_dropdown = Gtk.DropDown(model=output_model)
        output_dropdown.set_hexpand(True)
        try:
            output_dropdown.set_selected(output_names.index(self.config.local_output))
        except ValueError:
            output_dropdown.set_selected(0)
        output_label = Gtk.Label(label="Headphone output", xalign=0)
        output_label.add_css_class("field-label")
        audio_card.append(output_label)
        audio_card.append(output_dropdown)
        outer.append(audio_card)

        behavior_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        behavior_card.add_css_class("settings-card")
        behavior_title = Gtk.Label(label="Behavior", xalign=0)
        behavior_title.add_css_class("section-title")
        behavior_card.append(behavior_title)

        behavior_grid = Gtk.Grid(column_spacing=16, row_spacing=12)
        behavior_grid.set_column_homogeneous(False)
        behavior_card.append(behavior_grid)

        delay = Gtk.SpinButton.new_with_range(0.0, 3.0, 0.1)
        delay.set_digits(1)
        delay.set_value(self.config.playback_delay_seconds)
        delay_label = Gtk.Label(label="Playback delay", xalign=0)
        delay_label.add_css_class("field-label")
        behavior_grid.attach(delay_label, 0, 0, 1, 1)
        behavior_grid.attach(delay, 1, 0, 1, 1)
        seconds = Gtk.Label(label="seconds", xalign=0)
        seconds.add_css_class("field-help")
        behavior_grid.attach(seconds, 2, 0, 1, 1)

        debug = Gtk.CheckButton(label="Show debug error notifications")
        debug.set_active(self.config.debug_notifications)
        behavior_grid.attach(debug, 0, 1, 3, 1)

        shortcut = Gtk.Label(label="SUPER + ALT + T", xalign=0, selectable=True)
        shortcut.add_css_class("shortcut-chip")
        shortcut_label = Gtk.Label(label="Overlay shortcut", xalign=0)
        shortcut_label.add_css_class("field-label")
        behavior_grid.attach(shortcut_label, 0, 2, 1, 1)
        behavior_grid.attach(shortcut, 1, 2, 2, 1)
        outer.append(behavior_card)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        buttons.set_halign(Gtk.Align.END)
        test = Gtk.Button(label="Open message box")
        test.connect("clicked", lambda *_: self.show_overlay())
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")

        def save_settings(*_args: object) -> None:
            self.config.model_path = model_entry.get_text().strip()
            self.config.local_monitor = monitor.get_active()
            self.config.local_output = output_names[output_dropdown.get_selected()]
            self.config.playback_delay_seconds = delay.get_value()
            self.config.debug_notifications = debug.get_active()
            self.config.save()

        save.connect("clicked", save_settings)
        quit_button = Gtk.Button(label="Quit")
        quit_button.add_css_class("destructive-action")
        quit_button.connect("clicked", lambda *_: self.quit())
        buttons.append(quit_button)
        buttons.append(test)
        buttons.append(save)
        outer.append(buttons)
        window.set_child(outer)
        return window

    def _load_styles(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        css_path = Path(__file__).with_name("assets") / "style.css"
        provider = Gtk.CssProvider()
        provider.load_from_path(str(css_path))
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _browse_model(self, _button: Gtk.Button, entry: Gtk.Entry) -> None:
        chooser = Gtk.FileChooserNative(
            title="Choose a Piper voice model",
            transient_for=self.settings_window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Choose",
            cancel_label="Cancel",
        )
        file_filter = Gtk.FileFilter()
        file_filter.set_name("Piper models")
        file_filter.add_pattern("*.onnx")
        chooser.add_filter(file_filter)

        def selected(dialog: Gtk.FileChooserNative, response: int) -> None:
            if response == Gtk.ResponseType.ACCEPT:
                file = dialog.get_file()
                if file and file.get_path():
                    entry.set_text(file.get_path())
            dialog.destroy()

        chooser.connect("response", selected)
        chooser.show()

    def _send(self, *_args: object) -> None:
        if not self.entry:
            return
        text = self.entry.get_text().strip()
        if not text:
            return
        self.history.add(text)
        self.entry.set_text("")
        if self.overlay_window:
            self.overlay_window.hide()
        self.speech.submit(text)

    def _overlay_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if not self.entry:
            return False
        if keyval == Gdk.KEY_Escape:
            self.entry.set_text("")
            if self.overlay_window:
                self.overlay_window.hide()
            return True
        if keyval == Gdk.KEY_Up:
            self.entry.set_text(self.history.previous(self.entry.get_text()))
            self.entry.set_position(-1)
            return True
        if keyval == Gdk.KEY_Down:
            self.entry.set_text(self.history.next())
            self.entry.set_position(-1)
            return True
        return False

    def _speech_error(self, message: str) -> None:
        if not self.config.debug_notifications:
            return
        GLib.idle_add(self._notify_error, message)

    def _notify_error(self, message: str) -> bool:
        notification = Gio.Notification.new("Quick TTS Mic error")
        notification.set_body(message)
        self.send_notification(None, notification)
        return GLib.SOURCE_REMOVE

    def do_shutdown(self) -> None:
        self.speech.stop()
        super().do_shutdown()


def main() -> int:
    app = QuickTtsApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
