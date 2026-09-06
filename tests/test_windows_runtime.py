import io
import json
import struct
import threading
import wave
from dataclasses import replace

import pytest

from quick_tts_mic.windows_runtime import (WindowsConfig, WindowsSpeechQueue,
    discover_windows_models, parse_hotkey)
from quick_tts_mic.windows_audio import Endpoint, destinations, topology
from quick_tts_mic.windows_probe import ProbeError


def wav_bytes(samples=(0, 10000, -10000), rate=22050, channels=1, width=2):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(b''.join(int(s).to_bytes(width, 'little', signed=width != 1) for s in samples))
    return output.getvalue()


def test_legacy_config_preserves_separate_voice_and_unknown_settings(tmp_path):
    path = tmp_path / 'config.json'
    original = dict(model_path='C:/Voices/Alan.onnx', microsoft_voice_id='james-id',
                    local_output='legacy-pipewire-output', custom_setting={'kept': True})
    path.write_text(json.dumps(original))
    config = WindowsConfig.load(path)
    assert config.speech_provider == 'piper'
    for provider in ('microsoft', 'piper'):
        config.speech_provider = provider
        config.save(path)
        config = WindowsConfig.load(path)
        assert config.model_path == original['model_path']
        assert config.microsoft_voice_id == original['microsoft_voice_id']
    saved = json.loads(path.read_text())
    assert all(saved[k] == v for k, v in original.items())
    assert saved['debug_notifications'] is False
    assert '_extra' not in saved


@pytest.mark.parametrize('content', ['[]', 'null', 'broken', '42'])
def test_config_invalid_root(content, tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(content)
    assert WindowsConfig.load(path).speech_provider == 'piper'


def test_config_sanitizes_types_and_bounds(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(dict(local_monitor='false', speech_volume=500,
        output_rate=123, playback_delay_seconds=float('nan'), microsoft_voice_id=23)))
    config = WindowsConfig.load(path)
    assert not config.local_monitor
    assert config.speech_volume == 100
    assert config.output_rate == 48000
    assert config.playback_delay_seconds == 0.5
    assert config.microsoft_voice_id == ''


def test_model_discovery_requires_pair_and_retains_known_names(tmp_path):
    model = tmp_path / 'en_GB-alan-medium.onnx'
    model.touch()
    assert not discover_windows_models(directory=tmp_path)
    (tmp_path / (model.name + '.json')).write_text('{}')
    voices = discover_windows_models(directory=tmp_path)
    assert len(voices) == 1 and 'Alan' in voices[0].name


@pytest.mark.parametrize('shortcut', ['Win+T', 'T', 'Ctrl+Ctrl+T', 'Ctrl+Home', 'Ctrl+F25', 'Ctrl+é'])
def test_hotkey_rejects_invalid(shortcut):
    with pytest.raises(ProbeError):
        parse_hotkey(shortcut)


def test_hotkey_parse():
    assert parse_hotkey('Ctrl+Alt+T') == (0x4003, ord('T'))
    assert parse_hotkey('Shift+F24') == (0x4004, 0x87)


DEVICES = [Endpoint('message', 'Duplicate name', 2), Endpoint('preview', 'Duplicate name', 2)]


def config_for_routing():
    return WindowsConfig(message_endpoint_id='message', preview_endpoint_id='preview')


def test_exact_ids_allow_duplicate_names_and_deduplicate_monitor():
    config = config_for_routing()
    assert destinations(config, DEVICES) == [DEVICES[0]]
    config.local_monitor = True
    assert destinations(config, DEVICES) == DEVICES
    config.preview_endpoint_id = 'message'
    assert destinations(config, DEVICES) == [DEVICES[0]]


def test_missing_message_or_monitor_never_falls_back():
    config = config_for_routing()
    with pytest.raises(ProbeError):
        destinations(config, DEVICES[1:])
    config.local_monitor = True
    with pytest.raises(ProbeError):
        destinations(config, DEVICES[:1])


def test_preview_requires_current_verification_and_separate_endpoint():
    config = config_for_routing()
    verification = ('message', 'preview', topology(DEVICES))
    with pytest.raises(ProbeError):
        destinations(config, DEVICES, True)
    assert destinations(config, DEVICES, True, verification) == [DEVICES[1]]
    with pytest.raises(ProbeError):
        destinations(config, DEVICES + [Endpoint('new', 'USB', 2)], True, verification)
    config.message_endpoint_id = 'preview'
    with pytest.raises(ProbeError):
        destinations(config, DEVICES, True, verification)


def test_queue_fifo_snapshot_provider_switch_and_recovery():
    finished = threading.Event()
    received, errors = [], []
    class Engine:
        def synthesize(self, text, config):
            received.append((text, config.speech_provider, config.model_path, config.microsoft_voice_id))
            if text == 'fail':
                raise RuntimeError('SECRET message should not appear in errors')
            return wav_bytes()
    class Router:
        def validate(self, *args):
            pass
        def play(self, data, config, preview, verification, cancelled):
            if config.speech_provider == 'microsoft':
                finished.set()
    worker = WindowsSpeechQueue(errors.append, engine=Engine(), router=Router())
    config = WindowsConfig(model_path='model', microsoft_voice_id='voice', playback_delay_seconds=0)
    try:
        worker.submit('fail', config)
        config.speech_provider = 'microsoft'
        worker.submit('second', config)
        config.microsoft_voice_id = 'changed-after-submit'
        assert finished.wait(3)
    finally:
        worker.stop()
    assert received == [('fail', 'piper', 'model', 'voice'), ('second', 'microsoft', 'model', 'voice')]
    assert len(errors) == 1 and 'SECRET' not in errors[0]


def test_stop_interrupts_delay_and_prevents_playback():
    synthesized = threading.Event()
    played = []
    class Engine:
        def synthesize(self, *args):
            synthesized.set()
            return wav_bytes()
    class Router:
        def validate(self, *args): pass
        def play(self, *args): played.append(True)
    worker = WindowsSpeechQueue(lambda _: None, engine=Engine(), router=Router())
    worker.submit('text', WindowsConfig(playback_delay_seconds=30))
    assert synthesized.wait(3)
    worker.stop()
    assert not worker.thread.is_alive()
    assert not played


def test_legacy_home_config_migrates_without_overwriting_source(tmp_path, monkeypatch):
    from pathlib import Path
    from quick_tts_mic import windows_runtime as runtime
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    legacy = tmp_path / '.config' / 'quick-tts-mic' / 'config.json'
    legacy.parent.mkdir(parents=True)
    original = '{"model_path":"custom.onnx","microsoft_voice_id":"saved","other":23}'
    legacy.write_text(original)
    config = WindowsConfig.load()
    assert config.speech_provider == 'piper' and config.microsoft_voice_id == 'saved'
    assert legacy.read_text() == original
    assert json.loads(runtime.config_path().read_text())['other'] == 23
    config.model_path = 'changed.onnx'
    config.save()
    assert WindowsConfig.load().model_path == 'changed.onnx'
