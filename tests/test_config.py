from pathlib import Path

from quick_tts_mic.config import AppConfig


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    expected = AppConfig(
        model_path="/voices/test.onnx",
        local_monitor=False,
        local_output="speaker",
        speech_volume=35,
        playback_delay_seconds=0.8,
        debug_notifications=False,
    )
    expected.save(path)
    assert AppConfig.load(path) == expected


def test_invalid_config_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("not json")
    assert AppConfig.load(path) == AppConfig()


def test_existing_config_defaults_to_full_volume(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"local_monitor": false}')
    assert AppConfig.load(path).speech_volume == 100


def test_old_config_keeps_piper_and_adds_empty_microsoft_preference(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"model_path": "/custom/piper.onnx", "speech_volume": 42, "local_monitor": false}')
    config = AppConfig.load(path)
    assert config.microsoft_voice_id == ""
    assert config.model_path == "/custom/piper.onnx"
    config.microsoft_voice_id = "installed-or-missing-windows-id"
    config.save(path)
    restored = AppConfig.load(path)
    assert restored == config
    assert restored.speech_volume == 42
    assert restored.local_monitor is False
    restored.model_path = "/custom/another.onnx"
    restored.save(path)
    assert AppConfig.load(path).microsoft_voice_id == "installed-or-missing-windows-id"
