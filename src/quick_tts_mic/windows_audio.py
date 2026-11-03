"""WASAPI playback by exact endpoint ID. No system-default or fuzzy lookup."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import io
import math
import wave

from .windows_probe import ProbeError, wav_info


@dataclass(frozen=True)
class Endpoint:
    id: str
    name: str
    channels: int


def soundcard():
    import soundcard as sc
    return sc


def endpoints():
    return [Endpoint(s.id, s.name, s.channels) for s in soundcard().all_speakers()]


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


def decode_audio(data, rate, channels, volume):
    import numpy as np
    from scipy.signal import resample_poly
    info = wav_info(data)
    if info["channels"] not in (1, 2) or info["sample_width"] not in (1, 2, 3, 4):
        raise ProbeError("Unsupported speech WAV format; expected mono/stereo PCM.")
    if not math.isfinite(volume) or not 0 <= volume <= 1 or channels not in (1, 2) or rate not in (44100, 48000):
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
    if rate != info["sample_rate"]:
        divisor = math.gcd(rate, info["sample_rate"])
        samples = resample_poly(samples, rate // divisor, info["sample_rate"] // divisor, axis=0)
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
        return destinations(config, endpoints(), preview, verification)

    def play(self, data, config, preview, verification, cancelled):
        self.authorize(preview, verification)
        sc = soundcard()
        # Use objects from fresh enumeration directly: sc.get_speaker permits fuzzy matching.
        speakers = sc.all_speakers()
        devices = [Endpoint(s.id, s.name, s.channels) for s in speakers]
        selected = destinations(config, devices, preview, verification)
        buffers = [decode_audio(data, config.output_rate, min(2, d.channels), config.speech_volume / 100)
                   for d in selected]
        with ExitStack() as stack:
            players = []
            for device, buffer in zip(selected, buffers):
                speaker = exact_endpoint(speakers, device.id)
                players.append(stack.enter_context(speaker.player(
                    samplerate=config.output_rate, channels=buffer.shape[1],
                    blocksize=1024, exclusive_mode=False)))
            # Both streams open before any speech. Never retry another destination.
            if topology(endpoints()) != topology(devices):
                raise ProbeError("Audio devices changed. Reselect outputs and reverify previews.")
            for start in range(0, len(buffers[0]), 1024):
                if cancelled.is_set():
                    return
                self.authorize(preview, verification)
                for player, buffer in zip(players, buffers):
                    player.play(buffer[start:start + 1024])
