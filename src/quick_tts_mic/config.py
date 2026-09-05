from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from dataclasses import field
from pathlib import Path


APP_DIR = Path.home() / ".config" / "quick-tts-mic"
CONFIG_PATH = APP_DIR / "config.json"


def _default_model_path() -> str:
    override = os.environ.get("QUICK_TTS_MODEL")
    if override:
        return override
    development_model = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "voices"
        / "en_GB-alan-medium.onnx"
    )
    return str(development_model) if development_model.is_file() else ""


@dataclass(slots=True)
class AppConfig:
    model_path: str = field(default_factory=_default_model_path)
    local_monitor: bool = True
    local_output: str = ""
    speech_volume: int = 100
    playback_delay_seconds: float = 0.5
    debug_notifications: bool = True
    history_limit: int = 25
    microsoft_voice_id: str = ""

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        try:
            values = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in values.items() if key in allowed})

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
