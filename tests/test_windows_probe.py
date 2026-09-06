import io
import struct
import sys
from types import SimpleNamespace
import wave

import pytest

from quick_tts_mic import windows_probe as probe


def audio():
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        wav.writeframes(struct.pack('<hhh', 0, 32767, -32768))
    return output.getvalue()


def test_conversion_leadin_volume_and_channels():
    result = probe.convert_pcm(audio(), 44100, 2, 0)
    assert len(result) == (22050 + 6) * 2 * 2
    assert set(result) == {0}
    result = probe.convert_pcm(audio(), 44100, 2, 1)
    assert result[:22050 * 4] == bytes(22050 * 4)
    samples = struct.unpack('<' + 'h' * 12, result[22050 * 4:])
    assert samples[::2] == samples[1::2]
    assert min(samples) == -32768 and max(samples) == 32767


@pytest.mark.parametrize('volume', [-0.1, 1.1, float('nan'), float('inf')])
def test_invalid_volume(volume):
    with pytest.raises(probe.ProbeError): probe.convert_pcm(audio(), 48000, 2, volume)


def test_wav_truncated_and_no_overwrite(tmp_path):
    with pytest.raises(probe.ProbeError): probe.wav_info(audio()[:-2])
    path = tmp_path / 'speech.wav'
    probe.save_wav(audio(), path)
    with pytest.raises(FileExistsError): probe.save_wav(audio(), path)


def test_missing_voice_and_ambiguous_selection():
    for items in ([], [{'id': 'x'}, {'id': 'x'}]):
        with pytest.raises(probe.ProbeError): probe.exact_match(items, 'id', 'x')


def test_cli_non_windows_fails_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert probe.main(['voices']) == 1
    assert 'Windows runtime required' in capsys.readouterr().err


class FakeSD:
    def __init__(self, fail=False):
        self.opened = []
        self.fail = fail
    def query_hostapis(self): return [{'name': 'Windows WASAPI'}]
    def query_devices(self):
        return [dict(name='chosen', hostapi=0, max_output_channels=2, default_samplerate=48000)]
    def WasapiSettings(self, **kwargs): return kwargs
    def check_output_settings(self, **kwargs):
        assert kwargs['device'] == 0 and kwargs['extra_settings']['auto_convert'] is False
    def RawOutputStream(self, **kwargs):
        self.opened.append(kwargs)
        if self.fail: raise RuntimeError('disconnected')
        return self
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def write(self, pcm): return False


def test_explicit_playback_and_native_failure_never_retries():
    sd = FakeSD()
    result = probe.play_diagnostic(sd, audio(), 'chosen', 48000, 2, .2, True, 'message')
    assert len(sd.opened) == 1 and result['preview_enabled'] is False
    sd = FakeSD(fail=True)
    with pytest.raises(RuntimeError):
        probe.play_diagnostic(sd, audio(), 'chosen', 48000, 2, .2, True, 'message')
    assert len(sd.opened) == 1


@pytest.mark.parametrize('name,ack,purpose', [('missing', True, 'message'), ('chosen', False, 'message'), ('chosen', True, 'preview')])
def test_playback_fail_closed(name, ack, purpose):
    sd = FakeSD()
    with pytest.raises(probe.ProbeError):
        probe.play_diagnostic(sd, audio(), name, 48000, 2, .2, ack, purpose)
    assert not sd.opened


def test_windowed_probe_writes_failure_report(monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    report = tmp_path / 'report.json'
    assert probe.main(['--report', str(report), 'voices']) == 1
    assert json.loads(report.read_text())['ok'] is False


@pytest.mark.parametrize('short_read', [False, True])
def test_winrt_exact_voice_stream_and_cleanup(monkeypatch, short_read):
    import asyncio
    data = audio()
    events = []
    class Stream:
        size = len(data)
        def close(self): events.append('stream closed')
    class Synth:
        all_voices = [SimpleNamespace(id='selected'), SimpleNamespace(id='other')]
        async def synthesize_text_to_stream_async(self, text):
            assert self.voice.id == 'selected'
            assert text == probe.PHRASE
            return Stream()
        def close(self): events.append('synth closed')
    class Reader:
        def __init__(self, stream): pass
        async def load_async(self, size): return size - int(short_read)
        def read_bytes(self, destination): destination[:] = data
        def detach_stream(self): events.append('reader detached')
        def close(self): events.append('reader closed')
    monkeypatch.setitem(sys.modules, 'winrt.windows.media.speechsynthesis', SimpleNamespace(SpeechSynthesizer=Synth))
    monkeypatch.setitem(sys.modules, 'winrt.windows.storage.streams', SimpleNamespace(DataReader=Reader))
    if short_read:
        with pytest.raises(probe.ProbeError, match='Incomplete'):
            asyncio.run(probe.winrt_synthesize('selected'))
    else:
        assert asyncio.run(probe.winrt_synthesize('selected')) == data
    assert events == ['reader detached', 'reader closed', 'stream closed', 'synth closed']
    events.clear()
    with pytest.raises(probe.ProbeError): asyncio.run(probe.winrt_synthesize('missing'))
    assert events == []
