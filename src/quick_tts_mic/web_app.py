"""pywebview shell: settings and overlay as React/Watermelon pages over the speech core."""
from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import webview

from .config import AppConfig
from .microsoft_voices import discover_microsoft_voices
from .speech import SpeechQueue
from .voices import discover_voices


DIST_INDEX = Path(__file__).resolve().parents[2] / "web" / "dist" / "index.html"
# Fields the pages may change; everything else in the config stays Python-owned.
SETTABLE = {
    "model_path", "microsoft_voice_id", "local_monitor", "local_output",
    "speech_volume", "playback_delay_seconds", "debug_notifications",
}


class CasprWeb:
    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.speech = SpeechQueue(lambda: self.config, self.error)
        self.microsoft = discover_microsoft_voices()
        self.windows: dict[str, webview.Window] = {}

    def open(self, kind: str) -> None:
        if kind in self.windows:
            self.windows[kind].show()
            return
        url = os.environ.get("CASPR_WEB_URL") or str(DIST_INDEX)
        if kind == "overlay":
            window = webview.create_window(
                "Caspr", url, js_api=Api(self, kind), width=560, height=200,
                resizable=False, frameless=True, transparent=True, on_top=True,
                easy_drag=True,
            )
        else:
            window = webview.create_window(
                "Caspr TTS — Settings", url, js_api=Api(self, kind),
                width=620, height=760, min_size=(520, 560), background_color="#121c1b",
            )
        window.events.closed += lambda: self.windows.pop(kind, None)
        self.windows[kind] = window

    def set(self, name: str, value: object) -> None:
        if name not in SETTABLE:
            raise ValueError(f"Unknown setting: {name}")
        current = getattr(self.config, name)
        setattr(self.config, name, type(current)(value))
        self.config.save()
        self.broadcast("window.casprRefresh?.()")

    def state(self) -> dict:
        saved_ms = self.config.microsoft_voice_id
        return {
            "config": asdict(self.config),
            "voices": [
                {"id": v.model_path, "name": v.name, "detail": v.detail}
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
        if text.strip():
            self._app.speech.submit(text.strip())

    def sample(self) -> None:
        # Resolves the page's promise once the sample finishes playing.
        done = threading.Event()
        self._app.speech.sample(done.set)
        done.wait()

    def open_overlay(self) -> None:
        self._app.open("overlay")

    def close(self) -> None:
        window = self._app.windows.get(self._kind)
        if window:
            window.destroy()

    def quit(self) -> None:
        for window in list(self._app.windows.values()):
            window.destroy()


def main() -> int:
    app = CasprWeb()
    try:
        app.speech.router.ensure_virtual_mic()
    except Exception as error:
        app.error(str(error))
    app.open("overlay" if "overlay" in sys.argv[1:] else "settings")
    webview.start(debug=bool(os.environ.get("CASPR_WEB_DEBUG")))
    app.speech.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
