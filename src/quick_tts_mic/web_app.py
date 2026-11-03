"""pywebview shell: settings and overlay as React/Watermelon pages over the speech core."""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import threading
from dataclasses import asdict
from multiprocessing.connection import Client, Listener
from pathlib import Path

import webview

from .config import AppConfig, expand_slash_commands, normalize_quick_options
from .microsoft_voices import discover_microsoft_voices
from .speech import SpeechQueue
from .voices import discover_voices


DIST_INDEX = Path(__file__).resolve().parents[2] / "web" / "dist" / "index.html"
# One background instance owns the virtual mic; later launches just ask it to show a window.
INSTANCE_ADDRESS = (
    r"\\.\pipe\caspr-tts" if sys.platform == "win32"
    else str(Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "caspr-tts.sock")
)
# Fields the pages may change; everything else in the config stays Python-owned.
SETTABLE = {
    "model_path", "microsoft_voice_id", "local_monitor", "local_output",
    "speech_volume", "playback_delay_seconds", "debug_notifications", "quick_options",
}


class CasprWeb:
    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.speech = SpeechQueue(lambda: self.config, self.error)
        self.microsoft = discover_microsoft_voices()
        self.windows: dict[str, webview.Window] = {}
        self.focus_section = ""  # settings section to scroll to once its page loads

    def open(self, kind: str, hidden: bool = False) -> None:
        if kind in self.windows:
            window = self.windows[kind]
            # pywebview's GTK backend re-hides a window created hidden while this flag is set.
            window.hidden = False
            window.show()
            if kind == "overlay":
                self.windows[kind].run_js("document.querySelector('input')?.focus()")
            return
        url = os.environ.get("CASPR_WEB_URL") or str(DIST_INDEX)
        if kind == "overlay":
            window = webview.create_window(
                "Caspr", url, js_api=Api(self, kind), width=560, height=400,
                resizable=False, frameless=True, transparent=True, on_top=True,
                easy_drag=True, hidden=hidden,
            )
        else:
            window = webview.create_window(
                "Caspr TTS — Settings", url, js_api=Api(self, kind),
                width=620, height=760, min_size=(520, 560), background_color="#08090a",
            )
        window.events.closed += lambda: self.windows.pop(kind, None)
        self.windows[kind] = window

    def set(self, name: str, value: object) -> None:
        if name not in SETTABLE:
            raise ValueError(f"Unknown setting: {name}")
        if name == "quick_options":
            value = normalize_quick_options(value)
        else:
            value = type(getattr(self.config, name))(value)
        setattr(self.config, name, value)
        self.config.save()
        self.broadcast("window.casprRefresh?.()")

    def state(self) -> dict:
        saved_ms = self.config.microsoft_voice_id
        return {
            "config": asdict(self.config),
            "voices": [
                {"id": v.model_path, "name": v.name, "detail": v.detail, "gender": v.gender}
                for v in discover_voices(self.config.model_path)
            ],
            "outputs": [{"name": "", "description": "System default"}] + [
                {"name": o.name, "description": o.description}
                for o in self.speech.router.outputs()
            ],
            "microsoft": {
                "voices": [{"id": v.voice_id, "label": v.menu_label} for v in self.microsoft.voices],
                "status": self.microsoft.selection_status(saved_ms),
            },
            "discordInput": self.speech.router.discord_source_name,
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
        text = expand_slash_commands(text.strip(), self._app.config.quick_options)
        if text:
            self._app.speech.submit(text)
            if self._kind == "overlay":
                self.close()

    def speak_quick(self, index: int) -> None:
        """Speak a random phrase from quick option category `index` (its position in config)."""
        options = self._app.config.quick_options
        if 0 <= index < len(options) and options[index]["phrases"]:
            self.speak(random.choice(options[index]["phrases"]))

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

    def take_focus_section(self) -> str:
        section, self._app.focus_section = self._app.focus_section, ""
        return section

    def close(self) -> None:
        # Hide rather than destroy: the hidden overlay keeps the process (and virtual mic) alive.
        window = self._app.windows.get(self._kind)
        if window:
            window.hide()

    def quit(self) -> None:
        for window in list(self._app.windows.values()):
            window.destroy()


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
        app.speech.router.ensure_virtual_mic()
    except Exception as error:
        app.error(str(error))
    threading.Thread(target=_serve_instance, args=(app,), daemon=True).start()
    app.open("overlay", hidden=kind != "overlay")
    if kind == "settings":
        app.open("settings")
    webview.start(debug=bool(os.environ.get("CASPR_WEB_DEBUG")))
    app.speech.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
