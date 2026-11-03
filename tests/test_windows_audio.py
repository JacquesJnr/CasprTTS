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


def test_router_uses_exact_id_without_fuzzy_lookup(monkeypatch):
    calls = []
    class Speaker:
        name = 'same name'
        channels = 2
        def __init__(self, id): self.id = id
        def player(self, **kwargs):
            calls.append((self.id, kwargs))
            return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def play(self, data): pass
    speakers = [Speaker('message'), Speaker('preview')]
    monkeypatch.setattr(audio, 'soundcard', lambda: SimpleNamespace(all_speakers=lambda: speakers))
    config = WindowsConfig(message_endpoint_id='message', preview_endpoint_id='preview', local_monitor=True)
    audio.WindowsRouter().play(wav_data(), config, False, None, threading.Event())
    assert [c[0] for c in calls] == ['message', 'preview']
    assert all(c[1]['exclusive_mode'] is False for c in calls)
    calls.clear()
    config.message_endpoint_id = 'missing'
    with pytest.raises(ProbeError): audio.WindowsRouter().play(wav_data(), config, False, None, threading.Event())
    assert not calls


def test_preview_revocation_blocks_before_audio_open(monkeypatch):
    config = WindowsConfig(message_endpoint_id='message', preview_endpoint_id='preview')
    calls = []
    monkeypatch.setattr(audio, 'soundcard', lambda: calls.append('opened'))
    router = audio.WindowsRouter(preview_authorizer=lambda token: False)
    with pytest.raises(ProbeError, match='revoked'):
        router.play(wav_data(), config, True, ('old-token',), threading.Event())
    assert not calls
