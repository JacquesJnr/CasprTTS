import wave
from unittest.mock import Mock

import pytest

from quick_tts_mic.audio import PLAYBACK_PREROLL_SECONDS, _write_prerolled_wav
from quick_tts_mic.audio import PipeWireRouter, VIRTUAL_SINK


@pytest.mark.parametrize("channels,width,rate", [(1, 2, 22050), (2, 2, 48000), (1, 1, 16000)])
def test_preroll_preserves_entire_speech(tmp_path, channels, width, rate):
    source = tmp_path / "source.wav"
    output = tmp_path / "output.wav"
    speech = bytes(range(256)) * channels * width * 600
    with wave.open(str(source), "wb") as wav:
        wav.setparams((channels, width, rate, 0, "NONE", "not compressed"))
        wav.writeframes(speech)

    _write_prerolled_wav(str(source), str(output))

    with wave.open(str(output), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (
            channels, width, rate
        )
        preroll_frames = round(rate * PLAYBACK_PREROLL_SECONDS)
        silence = b"\x80" if width == 1 else b"\x00"
        assert wav.readframes(preroll_frames) == silence * preroll_frames * channels * width
        assert wav.readframes(wav.getnframes()) == speech


@pytest.mark.parametrize("volume,expected", [(0, 0), (25, 16384), (100, 65536), (-1, 0), (150, 65536)])
@pytest.mark.parametrize("monitor,output", [(False, ""), (True, ""), (True, "headphones")])
def test_playback_volume_reaches_each_output(monkeypatch, tmp_path, volume, expected, monitor, output):
    source = tmp_path / "speech.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x01\x00" * 100)
    router = PipeWireRouter()
    monkeypatch.setattr(router, "ensure_virtual_mic", lambda: None)
    popen = Mock(return_value=Mock(wait=Mock(return_value=0)))
    monkeypatch.setattr("quick_tts_mic.audio.subprocess.Popen", popen)

    router.play(str(source), monitor, output, volume=volume)

    commands = [call.args[0] for call in popen.call_args_list]
    assert len(commands) == (2 if monitor else 1)
    assert commands[0][2:4] == ["--device", VIRTUAL_SINK]
    for command in commands:
        assert command[1] == f"--volume={expected}"
    if monitor:
        assert commands[1][2:-1] == (["--device", output] if output else [])
