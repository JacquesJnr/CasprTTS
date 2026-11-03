from pathlib import Path

from quick_tts_mic.voices import discover_voices


def test_discovery_includes_external_current_voice(tmp_path: Path) -> None:
    model = tmp_path / "my_voice.onnx"
    model.touch()
    voices = discover_voices(str(model))
    external = next(voice for voice in voices if voice.model_path == str(model))
    assert external.name == "My Voice"
    assert external.detail == "Custom Piper voice"
    assert external.gender == ""


def test_default_voices_have_genders() -> None:
    from quick_tts_mic.voices import KNOWN_VOICES

    assert {gender for _name, _detail, gender in KNOWN_VOICES.values()} == {"male", "female"}
