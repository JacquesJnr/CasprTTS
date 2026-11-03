import builtins
import sys
from types import SimpleNamespace

import pytest

from quick_tts_mic import microsoft_voices


def install_api(monkeypatch, voices):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winrt.windows.media.speechsynthesis",
                        SimpleNamespace(SpeechSynthesizer=SimpleNamespace(all_voices=voices)))


def test_linux_never_imports_winrt(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert not name.startswith("winrt")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    result = microsoft_voices.discover_microsoft_voices()
    assert result.voices == ()
    assert "only on Windows" in result.unavailable_reason


def test_real_api_fields_and_stable_selection(monkeypatch):
    install_api(monkeypatch, [
        SimpleNamespace(id="installed-b", display_name="Same name", language="en-GB"),
        SimpleNamespace(id="installed-a", display_name="Same name", language="en-US"),
    ])
    result = microsoft_voices.discover_microsoft_voices()
    assert [v.voice_id for v in result.voices] == ["installed-b", "installed-a"]
    assert result.voices[0].menu_label == "Same name · en-GB"
    assert result.selected_index("installed-a") == 1
    assert result.selected_index("") is None
    assert result.selected_index("removed") is None
    assert "Your saved voice is unavailable" in result.selection_status("removed")
    assert not result.unavailable_reason


def test_empty_api_has_no_dummy_options(monkeypatch):
    install_api(monkeypatch, [])
    result = microsoft_voices.discover_microsoft_voices()
    assert not result.voices
    assert "No installed" in result.unavailable_reason


@pytest.mark.parametrize("error", [ImportError("missing"), OSError("native failure"), RuntimeError("projection failure")])
def test_optional_discovery_failures(monkeypatch, error):
    monkeypatch.setattr(sys, "platform", "win32")
    original = builtins.__import__

    def failing(name, *args, **kwargs):
        if name == "winrt.windows.media.speechsynthesis":
            raise error
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing)
    result = microsoft_voices.discover_microsoft_voices()
    assert not result.voices
    assert result.unavailable_reason


def test_iteration_failure_does_not_expose_partial_list(monkeypatch):
    def broken():
        yield SimpleNamespace(id="one", display_name="One", language="en-US")
        raise OSError("enumeration failed")

    install_api(monkeypatch, broken())
    result = microsoft_voices.discover_microsoft_voices()
    assert not result.voices
    assert "could not be loaded" in result.unavailable_reason


def test_gender_is_reported_when_available(monkeypatch):
    install_api(monkeypatch, [
        SimpleNamespace(id="james", display_name="Microsoft James", language="en-GB", gender=0),
        SimpleNamespace(id="hazel", display_name="Microsoft Hazel", language="en-GB", gender=1),
        SimpleNamespace(id="other", display_name="Other", language="en-US"),
    ])
    assert [v.gender for v in microsoft_voices.discover_microsoft_voices().voices] == ["male", "female", ""]
