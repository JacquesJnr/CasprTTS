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
        window.set_default_size(620, -1)
        window.set_resizable(False)
        window.set_hide_on_close(True)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        self.entry = Gtk.Entry(placeholder_text="Type something to say…")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._send)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._overlay_key_pressed)
        self.entry.add_controller(key_controller)

        send = Gtk.Button(label="Send")
        send.add_css_class("suggested-action")
        send.connect("clicked", self._send)

        box.append(self.entry)
        box.append(send)
        window.set_child(box)
        return window

    def _build_settings(self) -> Gtk.ApplicationWindow:
        window = Gtk.ApplicationWindow(application=self, title="Quick TTS Mic — Settings")
        window.set_default_size(620, 440)
        window.set_hide_on_close(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        title = Gtk.Label(label="Quick TTS Mic", xalign=0)
        title.add_css_class("title-1")
        outer.append(title)
        outer.append(Gtk.Label(
            label="Discord input: QuickTTS_Microphone",
            xalign=0,
            selectable=True,
        ))

        grid = Gtk.Grid(column_spacing=14, row_spacing=14)
        outer.append(grid)

        model_entry = Gtk.Entry(text=self.config.model_path, hexpand=True)
        grid.attach(Gtk.Label(label="Piper model (.onnx)", xalign=0), 0, 0, 1, 1)
        grid.attach(model_entry, 1, 0, 1, 1)

        browse = Gtk.Button(label="Browse…")
        browse.connect("clicked", self._browse_model, model_entry)
        grid.attach(browse, 2, 0, 1, 1)

        monitor = Gtk.CheckButton(label="Hear speech in headphones")
        monitor.set_active(self.config.local_monitor)
        grid.attach(monitor, 1, 1, 2, 1)

        output_names = [""]
        output_labels = ["System default"]
        for output in self.speech.router.outputs():
            output_names.append(output.name)
            output_labels.append(output.description)
        output_model = Gtk.StringList.new(output_labels)
        output_dropdown = Gtk.DropDown(model=output_model)
        try:
            output_dropdown.set_selected(output_names.index(self.config.local_output))
        except ValueError:
            output_dropdown.set_selected(0)
        grid.attach(Gtk.Label(label="Headphone output", xalign=0), 0, 2, 1, 1)
        grid.attach(output_dropdown, 1, 2, 2, 1)

        delay = Gtk.SpinButton.new_with_range(0.0, 3.0, 0.1)
        delay.set_digits(1)
        delay.set_value(self.config.playback_delay_seconds)
        grid.attach(Gtk.Label(label="Playback delay (seconds)", xalign=0), 0, 3, 1, 1)
        grid.attach(delay, 1, 3, 2, 1)

        debug = Gtk.CheckButton(label="Show debug error notifications")
        debug.set_active(self.config.debug_notifications)
        grid.attach(debug, 1, 4, 2, 1)

        shortcut = Gtk.Label(label="SUPER + ALT + T", xalign=0, selectable=True)
        grid.attach(Gtk.Label(label="Overlay shortcut", xalign=0), 0, 5, 1, 1)
        grid.attach(shortcut, 1, 5, 2, 1)

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
        quit_button.connect("clicked", lambda *_: self.quit())
        buttons.append(quit_button)
        buttons.append(test)
        buttons.append(save)
        outer.append(buttons)
        window.set_child(outer)
        return window

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
