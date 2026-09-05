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
from .voices import VoiceOption, discover_voices


APP_ID = "io.github.quickttsmic.App"


class QuickTtsApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.config = AppConfig.load()
        self.history = SessionHistory(self.config.history_limit)
        self.voices = discover_voices(self.config.model_path)
        self.speech = SpeechQueue(lambda: self.config, self._speech_error)
        self.settings_window: Gtk.ApplicationWindow | None = None
        self.overlay_window: Gtk.ApplicationWindow | None = None
        self.entry: Gtk.Entry | None = None
        self.overlay_voice_dropdown: Gtk.DropDown | None = None
        self.settings_voice_buttons: list[tuple[Gtk.CheckButton, VoiceOption]] = []

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
        window = Gtk.ApplicationWindow(application=self, title="Caspr")
        window.set_default_size(560, -1)
        window.set_resizable(False)
        window.set_hide_on_close(True)
        window.add_css_class("overlay-window")

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        shell.add_css_class("overlay-shell")
        shell.set_margin_top(10)
        shell.set_margin_bottom(10)
        shell.set_margin_start(10)
        shell.set_margin_end(10)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        icon.set_pixel_size(16)
        icon.add_css_class("brand-icon")
        heading.append(icon)

        heading_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        eyebrow = Gtk.Label(label="CASPR", xalign=0)
        eyebrow.add_css_class("eyebrow")
        heading_copy.append(eyebrow)
        heading_copy.set_hexpand(True)
        heading.append(heading_copy)

        self.overlay_voice_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new([voice.menu_label for voice in self.voices])
        )
        self.overlay_voice_dropdown.add_css_class("voice-switcher")
        self.overlay_voice_dropdown.set_tooltip_text("Voice for this and future messages")
        self.overlay_voice_dropdown.set_selected(self._selected_voice_index())
        self.overlay_voice_dropdown.connect("notify::selected", self._overlay_voice_changed)
        heading.append(self.overlay_voice_dropdown)
        shell.append(heading)

        self.entry = Gtk.Entry(placeholder_text="Type something to say…")
        self.entry.set_hexpand(True)
        self.entry.add_css_class("message-entry")
        self.entry.connect("activate", self._send)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._overlay_key_pressed)
        self.entry.add_controller(key_controller)

        shell.append(self.entry)

        footer = Gtk.Label(label="↵ Enter to speak     ·     ↑↓ history     ·     Esc dismiss", xalign=0)
        footer.add_css_class("footer-hint")
        shell.append(footer)
        window.set_child(shell)
        return window

    def _build_settings(self) -> Gtk.ApplicationWindow:
        window = Gtk.ApplicationWindow(application=self, title="Caspr TTS — Settings")
        window.set_default_size(620, 720)
        window.set_hide_on_close(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.add_css_class("settings-root")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        header_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        header_icon.set_pixel_size(20)
        header_icon.add_css_class("brand-icon")
        header.append(header_icon)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="CASPR", xalign=0)
        title.add_css_class("title")
        heading.append(title)
        subtitle = Gtk.Label(label="YOUR WORDS. A LITTLE MORE SOUL.", xalign=0)
        subtitle.add_css_class("subtitle")
        heading.append(subtitle)
        heading.set_hexpand(True)
        header.append(heading)

        status = Gtk.Label(label="TTS / OFFLINE")
        status.add_css_class("status-pill")
        status.set_valign(Gtk.Align.CENTER)
        header.append(status)
        outer.append(header)

        voice_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        voice_card.add_css_class("settings-card")
        voice_card.add_css_class("voice-card")
        voice_title = Gtk.Label(label="01 / Voice", xalign=0)
        voice_title.add_css_class("section-title")
        voice_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        voice_title.set_hexpand(True)
        voice_header.append(voice_title)
        sample = Gtk.Button(label="Sample voice")
        sample.add_css_class("suggested-action")
        sample.add_css_class("sample-button")
        sample.set_tooltip_text('Hear “I love text-to-speech” through headphones only')
        sample.set_sensitive(bool(self.voices))

        def sample_finished() -> bool:
            sample.set_label("Sample voice")
            sample.set_sensitive(bool(self.voices))
            return GLib.SOURCE_REMOVE

        def sample_voice(*_args: object) -> None:
            sample.set_sensitive(False)
            sample.set_label("Sampling…")
            self.speech.sample(lambda: GLib.idle_add(sample_finished))

        sample.connect("clicked", sample_voice)
        voice_header.append(sample)
        voice_card.append(voice_header)

        voice_group: Gtk.CheckButton | None = None
        self.settings_voice_buttons = []
        voice_grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        voice_grid.set_column_homogeneous(True)
        voice_card.append(voice_grid)
        for index, voice in enumerate(self.voices):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class("voice-choice")
            radio = Gtk.CheckButton()
            if voice_group is None:
                voice_group = radio
            else:
                radio.set_group(voice_group)
            radio.set_active(voice.model_path == self.config.model_path)
            row.append(radio)

            copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            copy.set_hexpand(True)
            name = Gtk.Label(label=voice.name, xalign=0)
            name.add_css_class("voice-name")
            copy.append(name)
            detail = Gtk.Label(label=voice.detail, xalign=0)
            detail.set_wrap(True)
            detail.add_css_class("field-help")
            copy.append(detail)
            row.append(copy)

            select_voice = Gtk.GestureClick()
            select_voice.connect(
                "released", lambda *_args, button=radio: button.set_active(True)
            )
            row.add_controller(select_voice)
            voice_grid.attach(row, index % 2, index // 2, 1, 1)
            self.settings_voice_buttons.append((radio, voice))
        outer.append(voice_card)

        audio_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        audio_card.add_css_class("settings-card")
        audio_card.add_css_class("audio-card")
        audio_title = Gtk.Label(label="02 / Audio", xalign=0)
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

        volume_label = Gtk.Label(label="Speech volume", xalign=0)
        volume_label.add_css_class("field-label")
        audio_card.append(volume_label)
        volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        volume.add_css_class("volume-scale")
        volume.set_hexpand(True)
        volume.set_draw_value(True)
        volume.set_digits(0)
        volume.set_value_pos(Gtk.PositionType.RIGHT)
        volume.set_format_value_func(lambda _scale, value: f"{value:.0f}%")
        volume.set_value(self.config.speech_volume)
        volume.set_tooltip_text("Speech volume for the virtual microphone and headphones")
        audio_card.append(volume)
        volume_help = Gtk.Label(
            label="Mic + headphones · 0% mutes · Applies to next playback", xalign=0,
            wrap=True,
        )
        volume_help.add_css_class("field-help")
        audio_card.append(volume_help)

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

        behavior_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        behavior_card.add_css_class("settings-card")
        behavior_card.add_css_class("behavior-card")
        behavior_title = Gtk.Label(label="03 / Behavior", xalign=0)
        behavior_title.add_css_class("section-title")
        behavior_card.append(behavior_title)

        behavior_grid = Gtk.Grid(column_spacing=12, row_spacing=8)
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
        buttons.add_css_class("settings-actions")
        buttons.set_halign(Gtk.Align.FILL)
        test = Gtk.Button(label="Open message box")
        test.connect("clicked", lambda *_: self.show_overlay())
        test.add_css_class("suggested-action")

        # Connect only after initial values are populated. Each control updates
        # its own setting so changing one never overwrites another control.
        for radio, voice in self.settings_voice_buttons:
            radio.connect(
                "toggled",
                lambda button, selected=voice: self._select_voice(selected.model_path)
                if button.get_active() else None,
            )
        monitor.connect("toggled", lambda widget: self._set_config_value(
            "local_monitor", widget.get_active()))
        output_dropdown.connect("notify::selected", lambda widget, _param:
            self._set_config_value("local_output", output_names[widget.get_selected()])
            if widget.get_selected() < len(output_names) else None)
        volume.connect("value-changed", lambda widget: self._set_config_value(
            "speech_volume", round(widget.get_value())))
        delay.connect("value-changed", lambda widget: self._set_config_value(
            "playback_delay_seconds", widget.get_value()))
        debug.connect("toggled", lambda widget: self._set_config_value(
            "debug_notifications", widget.get_active()))

        quit_button = Gtk.Button(label="Quit")
        quit_button.add_css_class("destructive-action")
        quit_button.connect("clicked", lambda *_: self.quit())
        buttons.append(quit_button)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        buttons.append(spacer)
        buttons.append(test)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(outer)
        scroller.set_vexpand(True)
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.append(scroller)
        frame.append(buttons)
        window.set_child(frame)
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

    def _selected_voice_index(self) -> int:
        for index, voice in enumerate(self.voices):
            if voice.model_path == self.config.model_path:
                return index
        return 0

    def _overlay_voice_changed(self, dropdown: Gtk.DropDown, _param: object) -> None:
        selected = dropdown.get_selected()
        if selected >= len(self.voices):
            return
        self._select_voice(self.voices[selected].model_path)

    def _set_config_value(self, name: str, value: object) -> None:
        if getattr(self.config, name) == value:
            return
        setattr(self.config, name, value)
        self.config.save()

    def _select_voice(self, model_path: str) -> None:
        if self.config.model_path == model_path:
            return
        self._set_config_value("model_path", model_path)
        if self.overlay_voice_dropdown:
            self.overlay_voice_dropdown.set_selected(self._selected_voice_index())
        for radio, voice in self.settings_voice_buttons:
            radio.set_active(voice.model_path == model_path)

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
        notification = Gio.Notification.new("Caspr TTS error")
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
