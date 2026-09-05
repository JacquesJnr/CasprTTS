"""Optional Windows voice discovery; this module does not provide playback."""
from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MicrosoftVoice:
    voice_id: str
    name: str
    language: str

    @property
    def menu_label(self) -> str:
        return f"{self.name} · {self.language}"


@dataclass(frozen=True, slots=True)
class MicrosoftVoiceDiscovery:
    voices: tuple[MicrosoftVoice, ...] = ()
    unavailable_reason: str = ""

    def selected_index(self, saved_id: str) -> int | None:
        return next((i for i, voice in enumerate(self.voices)
                     if voice.voice_id == saved_id), None)

    def selection_status(self, saved_id: str) -> str:
        if self.unavailable_reason:
            return self.unavailable_reason
        if saved_id and self.selected_index(saved_id) is None:
            return "Your saved voice is unavailable. Choose another installed voice."
        if not saved_id:
            return "Choose an installed Microsoft voice to save a preference."
        return "Microsoft voice preference saved."


def discover_microsoft_voices() -> MicrosoftVoiceDiscovery:
    if sys.platform != "win32":
        return MicrosoftVoiceDiscovery(unavailable_reason="Microsoft voices are available only on Windows.")
    try:
        # Lazy import keeps Windows projections entirely optional on Linux.
        from winrt.windows.media.speechsynthesis import SpeechSynthesizer

        voices = tuple(
            MicrosoftVoice(voice.id, voice.display_name, voice.language)
            for voice in SpeechSynthesizer.all_voices
        )
    except ImportError:
        return MicrosoftVoiceDiscovery(unavailable_reason="Microsoft voice support is not installed.")
    except Exception:
        # Optional native API/projection failures must never break Piper settings.
        return MicrosoftVoiceDiscovery(unavailable_reason="Microsoft voices could not be loaded.")
    if not voices:
        return MicrosoftVoiceDiscovery(unavailable_reason="No installed Microsoft voices were found.")
    return MicrosoftVoiceDiscovery(voices=voices)
