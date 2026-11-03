from pathlib import Path

from quick_tts_mic.config import AppConfig, expand_slash_commands, normalize_quick_options


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


def test_quick_options_are_normalized_and_capped(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"quick_options": [{"name": " Greeting ", "phrases": ["Hi", " ", 3, "Hey "]},'
        ' "junk", {"name": "No phrases"}, {}, {}, {}, {}]}'
    )
    assert AppConfig.load(path).quick_options == [
        {"name": "Greeting", "phrases": ["Hi", "Hey"]},
        {"name": "No phrases", "phrases": []},
        {"name": "", "phrases": []},
        {"name": "", "phrases": []},
        {"name": "", "phrases": []},
    ]
    assert normalize_quick_options("not a list") == []


def test_new_config_has_example_quick_option() -> None:
    assert AppConfig().quick_options[0]["name"] == "Greeting"


def test_slash_commands_expand_known_categories_only() -> None:
    options = [
        {"name": "Greeting", "phrases": ["Hey"]},
        {"name": "Good Night", "phrases": ["Night all"]},
        {"name": "Empty", "phrases": []},
    ]
    expand = lambda text: expand_slash_commands(text, options, choice=lambda p: p[0])
    assert expand("/greeting everyone, I'm back") == "Hey everyone, I'm back"
    assert expand("/GREETING /good-night") == "Hey Night all"
    assert expand("/empty and /unknown and a/greeting") == "/empty and /unknown and a/greeting"
