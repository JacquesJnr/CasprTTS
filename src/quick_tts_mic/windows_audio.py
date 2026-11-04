"""WASAPI playback through PortAudio (sounddevice), shared mode with Windows' own format conversion.

Outputs are identified by their exact WASAPI device name; no system-default or fuzzy lookup.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import io
import math
import threading
import wave

from .windows_probe import ProbeError, wav_info

WASAPI = "Windows WASAPI"
# PortAudio's device list is a snapshot; refreshing it (re-initialising PortAudio) while a stream
# is open would break playback, so listing and playing take turns.
_PORTAUDIO = threading.RLock()


@dataclass(frozen=True)
class Endpoint:
    id: str  # WASAPI device name, e.g. "Speakers (Realtek High Definition Audio(SST))"
    name: str
    channels: int


def sounddevice():
    import sounddevice as sd
    return sd


def _wasapi_outputs(sd):
    """(Endpoint, PortAudio index) for every WASAPI output device."""
    host = next((i for i, h in enumerate(sd.query_hostapis()) if h["name"] == WASAPI), None)
    if host is None:
        raise ProbeError("Windows WASAPI audio is unavailable.")
    return [(Endpoint(d["name"], d["name"], d["max_output_channels"]), index)
            for index, d in enumerate(sd.query_devices())
            if d["hostapi"] == host and d["max_output_channels"] > 0]


def endpoints(refresh=True):
    """WASAPI outputs. `refresh` re-initialises PortAudio to notice newly plugged-in devices
    (Settings listing); per-message checks skip it because it is slow."""
    sd = sounddevice()
    with _PORTAUDIO:
        if refresh:
            sd._terminate()
            sd._initialize()
        return [endpoint for endpoint, _ in _wasapi_outputs(sd)]


def topology(devices):
    return tuple(sorted((d.id, d.name, d.channels) for d in devices))


def exact_endpoint(devices, endpoint_id):
    matches = [device for device in devices if device.id == endpoint_id and endpoint_id]
    if len(matches) != 1:
        raise ProbeError("Selected output is missing or ambiguous. Select an output in Settings; no fallback was used.")
    return matches[0]


def destinations(config, devices, preview=False, verification=None):
    if preview:
        if not verification or verification != (config.message_endpoint_id, config.preview_endpoint_id, topology(devices)):
            raise ProbeError("Preview disabled. Verify capture isolation for these outputs in this session.")
        if config.message_endpoint_id == config.preview_endpoint_id:
            raise ProbeError("Preview requires a separate output from messages.")
        exact_endpoint(devices, config.message_endpoint_id)
        return [exact_endpoint(devices, config.preview_endpoint_id)]
    result = [exact_endpoint(devices, config.message_endpoint_id)]
    if config.local_monitor and config.preview_endpoint_id != config.message_endpoint_id:
        result.append(exact_endpoint(devices, config.preview_endpoint_id))
    return result


def decode_audio(data, channels, volume):
    """PCM WAV → float32 frames at the WAV's own rate, plus 0.5 s silence to wake the output.
    No resampling: WASAPI auto_convert adapts the rate to the device."""
    import numpy as np
    info = wav_info(data)
    rate = info["sample_rate"]
    if info["channels"] not in (1, 2) or info["sample_width"] not in (1, 2, 3, 4):
        raise ProbeError("Unsupported speech WAV format; expected mono/stereo PCM.")
    if not math.isfinite(volume) or not 0 <= volume <= 1 or channels not in (1, 2) or not 8000 <= rate <= 192000:
        raise ProbeError("Invalid output format or volume.")
    with wave.open(io.BytesIO(data), "rb") as wav:
        raw = wav.readframes(info["frames"])
    width = info["sample_width"]
    if width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif width == 3:
        parts = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        integers = parts[:, 0] | (parts[:, 1] << 8) | (parts[:, 2] << 16)
        samples = ((integers ^ 0x800000) - 0x800000).astype(np.float32) / 8388608
    else:
        samples = np.frombuffer(raw, dtype=f"<i{width}").astype(np.float32) / (1 << (width * 8 - 1))
    samples = samples.reshape(-1, info["channels"])
    if channels == 1:
        samples = samples.mean(axis=1, keepdims=True)
    elif info["channels"] == 1:
        samples = np.repeat(samples, 2, axis=1)
    samples = np.clip(samples * volume, -1, 1).astype(np.float32)
    return np.concatenate((np.zeros((rate // 2, channels), dtype=np.float32), samples))


class WindowsRouter:
    def __init__(self, preview_authorizer=None):
        self.preview_authorizer = preview_authorizer or (lambda token: False)

    def authorize(self, preview, verification):
        if preview and not self.preview_authorizer(verification):
            raise ProbeError("Preview verification expired or was revoked. Verify the route again.")

    def validate(self, config, preview=False, verification=None):
        self.authorize(preview, verification)
        return destinations(config, endpoints(refresh=False), preview, verification)

    def play(self, data, config, preview, verification, cancelled):
        self.authorize(preview, verification)
        sd = sounddevice()
        with _PORTAUDIO:
            devices = _wasapi_outputs(sd)
            selected = destinations(config, [endpoint for endpoint, _ in devices], preview, verification)
            index = {endpoint.id: i for endpoint, i in devices}
            # Speech is mono/stereo; auto_convert lets Windows' channel mixer and resampler fit it
            # to any device format (e.g. 4-channel laptop speakers, 44.1 kHz, 24-bit).
            settings = sd.WasapiSettings(exclusive=False, auto_convert=True)
            rate = wav_info(data)["sample_rate"]  # e.g. 22050 for Piper; auto_convert resamples
            buffers = [decode_audio(data, min(2, device.channels), config.speech_volume / 100)
                       for device in selected]
            with ExitStack() as stack:
                streams = [stack.enter_context(sd.OutputStream(
                    device=index[device.id], samplerate=rate, channels=buffer.shape[1],
                    dtype="float32", extra_settings=settings)) for device, buffer in zip(selected, buffers)]
                # Every stream is open before any speech. Never retry another destination.
                for start in range(0, len(buffers[0]), 1024):
                    if cancelled.is_set():
                        return
                    self.authorize(preview, verification)
                    for stream, buffer in zip(streams, buffers):
                        stream.write(buffer[start:start + 1024])
