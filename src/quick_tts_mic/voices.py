from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VoiceOption:
    name: str
    detail: str
    model_path: str

    @property
    def menu_label(self) -> str:
        return f"{self.name} · {self.detail}"


KNOWN_VOICES = {
    "en_GB-alan-medium": ("Alan", "British male · medium"),
    "en_GB-jenny_dioco-medium": ("Jenny", "Irish female · medium"),
    "en_US-amy-medium": ("Amy", "American female · medium"),
}


def discover_voices(current_model_path: str = "") -> list[VoiceOption]:
    voice_dir = Path(__file__).resolve().parents[2] / "data" / "voices"
    models = sorted(voice_dir.glob("*.onnx"))
    current = Path(current_model_path).expanduser() if current_model_path else None
    if current and current.is_file() and current not in models:
        models.append(current)

    voices: list[VoiceOption] = []
    for model in models:
        name, detail = KNOWN_VOICES.get(
            model.stem,
            (model.stem.replace("_", " ").replace("-", " ").title(), "Custom Piper voice"),
        )
        voices.append(VoiceOption(name=name, detail=detail, model_path=str(model)))
    return voices
