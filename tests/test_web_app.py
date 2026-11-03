from pathlib import Path
from types import SimpleNamespace

import pytest

from quick_tts_mic import web_app, windows_runtime
from quick_tts_mic.windows_probe import ProbeError
from quick_tts_mic.windows_runtime import WindowsConfig


def app_with(config, tmp_path: Path, monkeypatch):
    """CasprWeb without windows or speech: just the settings path."""
    monkeypatch.setattr(web_app, "SETTABLE", web_app.SETTABLE | {"hotkey"})
    app = object.__new__(web_app.CasprWeb)
    app.config, app.windows = config, {}
    changes = []
    app.hotkey = SimpleNamespace(change=changes.append)
    monkeypatch.setattr(windows_runtime, "config_path", lambda: tmp_path / "config.json")
    return app, changes


def test_rejects_unknown_settings_and_invalid_hotkeys(tmp_path, monkeypatch):
    app, changes = app_with(WindowsConfig(), tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        app.set("history_limit", 999)
    with pytest.raises(ProbeError):
        app.set("hotkey", "Win+T")
    assert app.config.hotkey == "Ctrl+Alt+T" and changes == []


def test_valid_hotkey_is_saved_and_reregistered(tmp_path, monkeypatch):
    app, changes = app_with(WindowsConfig(), tmp_path, monkeypatch)
    app.set("hotkey", "Ctrl+Shift+F9")
    assert app.config.hotkey == "Ctrl+Shift+F9" and changes == ["Ctrl+Shift+F9"]
    assert WindowsConfig.load(tmp_path / "config.json").hotkey == "Ctrl+Shift+F9"
