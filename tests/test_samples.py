import threading
import wave
from unittest.mock import Mock

import pytest

from quick_tts_mic.audio import AudioError, AudioOutput, PipeWireRouter, VIRTUAL_SINK
from quick_tts_mic.config import AppConfig
from quick_tts_mic.speech import SpeechQueue


@pytest.mark.parametrize('selected,default', [('', 'headphones'), ('', VIRTUAL_SINK), ('headphones', VIRTUAL_SINK)])
def test_samples_only_play_to_explicit_local_output(tmp_path, monkeypatch, selected, default):
    source = tmp_path / 'sample.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\x01\x00' * 100)
    router = PipeWireRouter()
    monkeypatch.setattr(router, 'outputs', lambda: [AudioOutput('headphones', 'Headphones')])
    ensure = Mock()
    monkeypatch.setattr(router, 'ensure_virtual_mic', ensure)
    run = Mock(return_value=Mock(returncode=0, stdout=default))
    monkeypatch.setattr('quick_tts_mic.audio.subprocess.run', run)
    router.play_sample(str(source), selected, 25)
    command = run.call_args.args[0]
    assert command[:4] == ['paplay', '--volume=16384', '--device', 'headphones']
    assert VIRTUAL_SINK not in command
    ensure.assert_not_called()


@pytest.mark.parametrize('selected', ['', VIRTUAL_SINK, 'disconnected-headphones'])
def test_sample_fails_without_safe_output(monkeypatch, selected):
    router = PipeWireRouter()
    monkeypatch.setattr(router, 'outputs', lambda: [])
    run = Mock(return_value=Mock(returncode=0, stdout=VIRTUAL_SINK))
    monkeypatch.setattr('quick_tts_mic.audio.subprocess.run', run)
    with pytest.raises(AudioError, match='headphone output'):
        router.play_sample('unused.wav', selected)
    assert all(call.args[0][0] != 'paplay' for call in run.call_args_list)


@pytest.mark.parametrize('fails', [False, True])
def test_sample_uses_click_time_voice_and_never_normal_route(fails):
    config = AppConfig(model_path='selected.onnx', local_monitor=False, speech_volume=37)
    started, resume, done = threading.Event(), threading.Event(), threading.Event()
    def synthesize(*_args):
        started.set()
        assert resume.wait(2)
    engine = Mock(synthesize=Mock(side_effect=synthesize))
    router = Mock()
    if fails:
        router.play_sample.side_effect = AudioError('Unavailable output')
    errors = Mock()
    queue = SpeechQueue(lambda: config, errors, router=router, engine=engine)
    try:
        queue.sample(done.set)
        assert started.wait(2)
        config.model_path = 'different.onnx'
        config.speech_volume = 90
        resume.set()
        assert done.wait(2)
        assert engine.synthesize.call_args.args[:2] == ('I love text-to-speech', 'selected.onnx')
        assert router.play_sample.call_args.kwargs == {'local_output': '', 'volume': 37}
        router.play.assert_not_called()
        assert errors.call_count == int(fails)
    finally:
        resume.set()
        queue.stop()
