"""pywebview shell: settings and overlay as React/Watermelon pages over the speech core."""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import threading
import traceback
from dataclasses import asdict
from multiprocessing.connection import Client, Listener
from pathlib import Path

import webview

from .config import AppConfig, expand_slash_commands, normalize_quick_options
from .history import SessionHistory
from .microsoft_voices import discover_microsoft_voices

WINDOWS = sys.platform == "win32"


# Frozen (PyInstaller) builds unpack web/dist under sys._MEIPASS; source checkouts use the repo.
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DIST_INDEX = _ROOT / "web" / "dist" / "index.html"
# One background instance owns the virtual mic; later launches just ask it to show a window.
INSTANCE_ADDRESS = (
    r"\\.\pipe\caspr-tts" if WINDOWS
    else str(Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "caspr-tts.sock")
)
# Fields the pages may change; everything else in the config stays Python-owned.
SETTABLE = {
    "model_path", "microsoft_voice_id", "local_monitor", "speech_volume",
    "playback_delay_seconds", "debug_notifications", "quick_options",
    *(("speech_provider", "message_endpoint_id", "preview_endpoint_id", "hotkey") if WINDOWS
      else ("local_output",)),
}


def window_options(kind: str) -> dict:
    """pywebview create_window arguments per window; the Windows smoke test renders these too."""
    if kind == "overlay":
        return dict(title="Caspr", width=560, height=400, resizable=False, frameless=True,
                    transparent=True, on_top=True, easy_drag=True)
    return dict(title="Caspr TTS — Settings", width=620, height=760, min_size=(520, 560),
                background_color="#08090a")


class LinuxBackend:
    """PipeWire virtual mic + Piper (Windows: windows_runtime.WindowsBackend)."""

    def __init__(self, config_provider, error_callback) -> None:
        from .speech import SpeechQueue
        self.queue = SpeechQueue(config_provider, error_callback)
        self.discord_input = self.queue.router.discord_source_name

    def prepare(self) -> None:
        self.queue.router.ensure_virtual_mic()

    def submit(self, text: str) -> None:
        self.queue.submit(text)

    def sample(self, on_complete) -> None:
        self.queue.sample(on_complete)

    def stop(self) -> None:
        self.queue.stop()

    def outputs(self) -> list[dict]:
        return [{"name": "", "description": "System default"}] + [
            {"name": o.name, "description": o.description} for o in self.queue.router.outputs()
        ]

    def voices(self, config: AppConfig) -> list:
        from .voices import discover_voices
        return discover_voices(config.model_path)


def _platform():
    if WINDOWS:
        from .windows_runtime import WindowsBackend, WindowsConfig
        return WindowsConfig, WindowsBackend
    return AppConfig, LinuxBackend


class CasprWeb:
    def __init__(self) -> None:
        config_class, backend_class = _platform()
        self.config = config_class.load()
        self.speech = backend_class(lambda: self.config, self.error)
        self.history = SessionHistory(self.config.history_limit)  # typed messages, this session only
        self.microsoft = discover_microsoft_voices()
        self.windows: dict[str, webview.Window] = {}
        self.focus_section = ""  # settings section to scroll to once its page loads
        self.hotkey = None  # Windows: global shortcut (Linux binds it in the desktop instead)
        self.tray = None

    def open(self, kind: str, hidden: bool = False) -> None:
        if kind in self.windows:
            window = self.windows[kind]
            # pywebview's GTK backend re-hides a window created hidden while this flag is set.
            window.hidden = False
            window.show()
            if kind == "overlay":
                self.history.reset_navigation()
                self.windows[kind].run_js("document.querySelector('input')?.focus()")
            return
        url = os.environ.get("CASPR_WEB_URL") or str(DIST_INDEX)
        window = webview.create_window(url=url, js_api=Api(self, kind), hidden=hidden,
                                       **window_options(kind))
        window.events.closed += lambda: self.windows.pop(kind, None)
        self.windows[kind] = window

    def set(self, name: str, value: object) -> None:
        if name not in SETTABLE:
            raise ValueError(f"Unknown setting: {name}")
        if name == "quick_options":
            value = normalize_quick_options(value)
        else:
            value = type(getattr(self.config, name))(value)
        if name == "hotkey":
            from .windows_runtime import parse_hotkey
            parse_hotkey(value)  # raises a readable error for the page
        setattr(self.config, name, value)
        self.config.save()
        if name == "hotkey" and self.hotkey:
            self.hotkey.change(value)
        self.broadcast("window.casprRefresh?.()")

    def notify(self, message: str) -> None:
        """Always-visible message: a tray balloon on Windows, the error channel elsewhere."""
        if self.tray:
            self.tray.notify(message, "Caspr TTS")
        else:
            self.error(message)

    def quit(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
        if self.tray:
            self.tray.stop()
        for window in list(self.windows.values()):
            window.destroy()

    def state(self) -> dict:
        saved_ms = self.config.microsoft_voice_id
        errors: list[str] = []

        def part(label, read, default):
            # One failing source (e.g. audio device enumeration) must not blank the whole page.
            try:
                return read()
            except Exception as error:
                traceback.print_exc()
                errors.append(f"{label}: {error}")
                return default

        return {
            "platform": "windows" if WINDOWS else "linux",
            "config": {k: v for k, v in asdict(self.config).items() if not k.startswith("_")},
            "voices": part("Voices", lambda: [
                {"id": v.model_path, "name": v.name, "detail": v.detail, "gender": v.gender}
                for v in self.speech.voices(self.config)
            ], []),
            "outputs": part("Audio outputs", self.speech.outputs, []),
            "errors": errors,
            "microsoft": {
                "voices": [{"id": v.voice_id, "label": v.menu_label, "name": v.name,
                            "language": v.language, "gender": v.gender} for v in self.microsoft.voices],
                "status": self.microsoft.selection_status(saved_ms),
            },
            "discordInput": self.speech.discord_input,
        }

    def broadcast(self, js: str) -> None:
        for window in list(self.windows.values()):
            window.run_js(js)

    def error(self, message: str) -> None:
        print(f"caspr: {message}", file=sys.stderr)
        if self.config.debug_notifications:
            self.broadcast(f"window.casprError?.({json.dumps(message)})")


class Api:
    """One per window; pywebview exposes the public methods to that page's JS."""

    def __init__(self, app: CasprWeb, kind: str) -> None:
        self._app = app
        self._kind = kind

    def kind(self) -> str:
        return self._kind

    def state(self) -> dict:
        return self._app.state()

    def set(self, name: str, value: object) -> None:
        self._app.set(name, value)

    def speak(self, text: str) -> None:
        """Speak a typed message; it is kept in history as typed, so /commands re-roll."""
        self._app.history.add(text)
        self._submit(text)

    def speak_quick(self, index: int) -> None:
        """Speak a random phrase from quick option category `index` (its position in config)."""
        options = self._app.config.quick_options
        if 0 <= index < len(options) and options[index]["phrases"]:
            self._submit(random.choice(options[index]["phrases"]))

    def history_previous(self, current: str) -> str:
        return self._app.history.previous(current)

    def history_next(self) -> str:
        return self._app.history.next()

    def _submit(self, text: str) -> None:
        text = expand_slash_commands(text.strip(), self._app.config.quick_options)
        if text:
            self._app.speech.submit(text)
            if self._kind == "overlay":
                self.close()

    def sample(self) -> None:
        # Resolves the page's promise once the sample finishes playing.
        done = threading.Event()
        self._app.speech.sample(done.set)
        done.wait()

    def open_overlay(self) -> None:
        self._app.open("overlay")

    def open_settings(self, section: str = "") -> None:
        app = self._app
        if "settings" in app.windows:
            app.open("settings")
            app.windows["settings"].run_js(f"window.casprFocus?.({json.dumps(section)})")
        else:
            app.focus_section = section
            app.open("settings")
        if self._kind == "overlay":
            self.close()

    def open_voices_folder(self) -> None:
        """Windows: Piper models live in %LOCALAPPDATA%\\Caspr TTS\\data\\voices; open it in Explorer."""
        from .windows_runtime import voice_dir
        voice_dir().mkdir(parents=True, exist_ok=True)
        os.startfile(voice_dir())  # type: ignore[attr-defined]  # Windows only

    def take_focus_section(self) -> str:
        section, self._app.focus_section = self._app.focus_section, ""
        return section

    def close(self) -> None:
        # Hide rather than destroy: the hidden overlay keeps the process (and virtual mic) alive.
        window = self._app.windows.get(self._kind)
        if window:
            window.hide()

    def quit(self) -> None:
        self._app.quit()


def _forward_to_running(kind: str) -> bool:
    try:
        with Client(INSTANCE_ADDRESS) as conn:
            conn.send_bytes(kind.encode())
        return True
    except OSError:
        return False


def _serve_instance(app: CasprWeb) -> None:
    if sys.platform != "win32":
        Path(INSTANCE_ADDRESS).unlink(missing_ok=True)  # stale socket from a crashed run
    with Listener(INSTANCE_ADDRESS) as listener:
        while True:
            with listener.accept() as conn:
                kind = conn.recv_bytes(16).decode()
            if kind in ("overlay", "settings"):
                app.open(kind)


def main() -> int:
    kind = "overlay" if "overlay" in sys.argv[1:] else "settings"
    if _forward_to_running(kind):
        return 0
    app = CasprWeb()
    try:
        app.speech.prepare()
    except Exception as error:
        app.error(str(error))
    threading.Thread(target=_serve_instance, args=(app,), daemon=True).start()
    if WINDOWS:
        from .windows_shell import WindowsHotkey, start_tray
        app.tray = start_tray(lambda: app.open("overlay"), lambda: app.open("settings"), app.quit)
        app.hotkey = WindowsHotkey(app.config.hotkey, lambda: app.open("overlay"), app.notify)
    app.open("overlay", hidden=kind != "overlay")
    if kind == "settings":
        app.open("settings")
    # Serve web/dist over pywebview's localhost server: WebView2 (Chromium) refuses ES-module
    # scripts from file:// pages, which left Windows windows blank.
    webview.start(debug=bool(os.environ.get("CASPR_WEB_DEBUG")), http_server=True)
    app.speech.stop()
    # pywebview's localhost server leaves non-daemon threads behind; without a hard exit the
    # process lingers after Quit, still owning the single-instance pipe, so relaunches do nothing.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
