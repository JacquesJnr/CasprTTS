import io
import struct
import threading
from types import SimpleNamespace
import wave

import pytest
np = pytest.importorskip('numpy')
pytest.importorskip('scipy')
from quick_tts_mic import windows_audio as audio
from quick_tts_mic.windows_runtime import WindowsConfig
from quick_tts_mic.windows_probe import ProbeError


def wav_data(rate=22050, channels=1, width=2):
    output = io.BytesIO()
    raw = bytes([128, 255, 0] * 100) if width == 1 else b''.join(
        v.to_bytes(width, 'little', signed=True) for v in [0, 2 ** (width * 8 - 2), -(2 ** (width * 8 - 2))] * 100)
    with wave.open(output, 'wb') as wav:
        wav.setparams((channels, width, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes(raw)
    return output.getvalue()


@pytest.mark.parametrize('rate', [44100, 48000])
@pytest.mark.parametrize('width', [1, 2, 3, 4])
def test_resampling_pcm_formats_and_silence(rate, width):
    result = audio.decode_audio(wav_data(width=width), rate, 2, .5)
    assert result.dtype == np.float32 and result.shape[1] == 2
    assert np.all(result[:rate // 2] == 0)
    assert np.array_equal(result[:, 0], result[:, 1])
    assert .1 < np.max(np.abs(result)) <= 1
    assert np.all(audio.decode_audio(wav_data(width=width), rate, 1, 0) == 0)


def test_stereo_to_mono():
    data = audio.decode_audio(wav_data(channels=2), 48000, 1, 1)
    assert data.shape[1] == 1


class FakeSounddevice:
    """Two WASAPI outputs plus an MME duplicate name that must never be picked."""

    def __init__(self):
        self.opened = []

    def query_hostapis(self):
        return [{'name': 'MME'}, {'name': 'Windows WASAPI'}]

    def query_devices(self):
        return [{'name': 'message', 'hostapi': 0, 'max_output_channels': 2},
                {'name': 'message', 'hostapi': 1, 'max_output_channels': 4},
                {'name': 'preview', 'hostapi': 1, 'max_output_channels': 2},
                {'name': 'mic', 'hostapi': 1, 'max_output_channels': 0}]

    def _terminate(self): pass
    def _initialize(self): pass

    def WasapiSettings(self, **kwargs):
        return kwargs

    def OutputStream(self, **kwargs):
        self.opened.append(kwargs)
        return self

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def write(self, data): pass


def test_lists_wasapi_outputs_only():
    fake = FakeSounddevice()
    assert [(e.id, e.channels, i) for e, i in audio._wasapi_outputs(fake)] == [('message', 4, 1), ('preview', 2, 2)]


def test_router_plays_exact_wasapi_devices_with_auto_convert(monkeypatch):
    fake = FakeSounddevice()
    monkeypatch.setattr(audio, 'sounddevice', lambda: fake)
    config = WindowsConfig(message_endpoint_id='message', preview_endpoint_id='preview', local_monitor=True)
    audio.WindowsRouter().play(wav_data(), config, False, None, threading.Event())
    # Index 1 (WASAPI 'message'), not the MME device of the same name; stereo even on 4 channels.
    assert [(o['device'], o['channels']) for o in fake.opened] == [(1, 2), (2, 2)]
    assert all(o['extra_settings'] == {'exclusive': False, 'auto_convert': True} for o in fake.opened)
    fake.opened.clear()
    config.message_endpoint_id = 'missing'
    with pytest.raises(ProbeError): audio.WindowsRouter().play(wav_data(), config, False, None, threading.Event())
    assert not fake.opened


def test_preview_revocation_blocks_before_audio_open(monkeypatch):
    config = WindowsConfig(message_endpoint_id='message', preview_endpoint_id='preview')
    fake = FakeSounddevice()
    monkeypatch.setattr(audio, 'sounddevice', lambda: fake)
    router = audio.WindowsRouter(preview_authorizer=lambda token: False)
    with pytest.raises(ProbeError, match='revoked'):
        router.play(wav_data(), config, True, ('old-token',), threading.Event())
    assert not fake.opened
