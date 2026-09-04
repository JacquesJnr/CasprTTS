from pathlib import Path

from quick_tts_mic.config import AppConfig


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    expected = AppConfig(
        model_path="/voices/test.onnx",
        local_monitor=False,
        local_output="speaker",
        playback_delay_seconds=0.8,
        debug_notifications=False,
    )
    expected.save(path)
    assert AppConfig.load(path) == expected


def test_invalid_config_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("not json")
    assert AppConfig.load(path) == AppConfig()

