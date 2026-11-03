from __future__ import annotations

import json
import os
import random
import re
from dataclasses import asdict, dataclass
from dataclasses import field
from pathlib import Path
from typing import Callable


APP_DIR = Path.home() / ".config" / "quick-tts-mic"
CONFIG_PATH = APP_DIR / "config.json"
MAX_QUICK_OPTIONS = 5


def normalize_quick_options(value: object) -> list[dict]:
    """Keep at most five {name, phrases} categories with string fields; drop malformed entries."""
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        phrases = item.get("phrases")
        result.append({
            "name": str(item.get("name", "")).strip(),
            "phrases": [p.strip() for p in phrases if isinstance(p, str) and p.strip()]
            if isinstance(phrases, list) else [],
        })
    return result[:MAX_QUICK_OPTIONS]


# A /command starts a word; web/src/commands.ts mirrors this for highlighting.
SLASH_COMMAND = re.compile(r"(?<!\S)/([\w-]+)")


def command_slug(name: str) -> str:
    return re.sub(r"\s+", "-", name.strip().lower())


def expand_slash_commands(
    text: str, quick_options: list[dict], choice: Callable[[list[str]], str] = random.choice,
) -> str:
    """Replace each /category with a random phrase from it; unknown commands stay as typed."""
    phrases = {command_slug(o["name"]): o["phrases"] for o in quick_options if o["name"] and o["phrases"]}

    def replace(match: re.Match[str]) -> str:
        options = phrases.get(match.group(1).lower())
        return choice(options) if options else match.group(0)

    return SLASH_COMMAND.sub(replace, text)


def _default_quick_options() -> list[dict]:
    return [{"name": "Greeting", "phrases": ["Hello", "Hi", "Hey", "Wassup", "HEYA"]}]


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
    quick_options: list[dict] = field(default_factory=_default_quick_options)

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        try:
            values = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        config = cls(**{key: value for key, value in values.items() if key in allowed})
        config.quick_options = normalize_quick_options(config.quick_options)
        return config

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
