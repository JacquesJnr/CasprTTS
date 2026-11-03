"""Isolated feasibility CLI. Never imports the GTK app or saves app preferences."""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import platform
import struct
import sys
import wave
from pathlib import Path

PHRASE = "I love text-to-speech"


class ProbeError(RuntimeError):
    pass


def exact_match(items, key, value):
    matches = [item for item in items if item[key] == value]
    if len(matches) != 1:
        raise ProbeError(f"Selection must match exactly one {key}; found {len(matches)}. No fallback.")
    return matches[0]


def wav_info(data):
    with wave.open(io.BytesIO(data), "rb") as wav:
        info = dict(channels=wav.getnchannels(), sample_width=wav.getsampwidth(),
                    sample_rate=wav.getframerate(), frames=wav.getnframes())
        if wav.getcomptype() != "NONE" or not info["frames"]:
            raise ProbeError("Expected nonempty uncompressed PCM WAV.")
        frames = wav.readframes(info["frames"])
        if len(frames) != info["frames"] * info["channels"] * info["sample_width"]:
            raise ProbeError("Truncated WAV.")
        info["duration_seconds"] = info["frames"] / info["sample_rate"]
        return info


def convert_pcm(data, rate, channels, volume):
    """Diagnostic linear resampler, mono/stereo only; adds 0.5 s silence.

    This intentionally simple converter is not the production quality resampler.
    """
    if rate not in (44100, 48000) or channels not in (1, 2):
        raise ProbeError("Diagnostic output must be 44100/48000 Hz, mono/stereo.")
    if not math.isfinite(volume) or not 0 <= volume <= 1:
        raise ProbeError("Volume must be finite and between 0 and 1.")
    info = wav_info(data)
    if info["channels"] not in (1, 2) or info["sample_width"] not in (1, 2, 3, 4):
        raise ProbeError("Only 8/16/24/32-bit mono/stereo PCM is supported.")
    if info["duration_seconds"] > 60:
        raise ProbeError("Diagnostic WAV must be at most 60 seconds.")
    with wave.open(io.BytesIO(data), "rb") as wav:
        raw = wav.readframes(info["frames"])
    width, source_channels = info["sample_width"], info["channels"]
    samples = []
    for pos in range(0, len(raw), width * source_channels):
        frame = []
        for channel in range(source_channels):
            part = raw[pos + channel * width:pos + (channel + 1) * width]
            value = (part[0] - 128) / 128 if width == 1 else int.from_bytes(
                part, "little", signed=True) / (1 << (width * 8 - 1))
            frame.append(value)
        samples.append(frame)
    output = bytearray(rate // 2 * channels * 2)
    count = max(1, round(info["frames"] * rate / info["sample_rate"]))
    for i in range(count):
        position = min(i * info["sample_rate"] / rate, len(samples) - 1)
        left = int(position)
        fraction = position - left
        right = min(left + 1, len(samples) - 1)
        frame = [a + (b - a) * fraction for a, b in zip(samples[left], samples[right])]
        if channels == 1:
            frame = [sum(frame) / len(frame)]
        elif source_channels == 1:
            frame *= 2
        for value in frame:
            output.extend(struct.pack("<h", max(-32768, min(32767, round(value * volume * 32768)))))
    return bytes(output)


def winrt_voices():
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    return [dict(id=v.id, name=v.display_name, language=v.language)
            for v in SpeechSynthesizer.all_voices]


async def winrt_synthesize(voice_id, text=PHRASE):
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    from winrt.windows.storage.streams import DataReader
    voices = list(SpeechSynthesizer.all_voices)
    selected = exact_match([dict(id=v.id, voice=v) for v in voices], "id", voice_id)
    synth = SpeechSynthesizer()
    try:
        synth.voice = selected["voice"]
        stream = await synth.synthesize_text_to_stream_async(text)
        try:
            reader = DataReader(stream)
            try:
                size = int(stream.size)
                if not 0 < size <= 32 * 1024 * 1024:
                    raise ProbeError("Unexpected synthesis stream size.")
                loaded = await reader.load_async(size)
                if loaded != size:
                    raise ProbeError("Incomplete synthesis stream.")
                data = bytearray(size)
                reader.read_bytes(data)
                return bytes(data)
            finally:
                reader.detach_stream()
                reader.close()
        finally:
            stream.close()
    finally:
        synth.close()


async def windows_endpoints():
    from winrt.windows.devices.enumeration import DeviceInformation
    from winrt.windows.media.devices import MediaDevice
    result = {}
    for kind, selector in (("render", MediaDevice.get_audio_render_selector()),
                           ("capture", MediaDevice.get_audio_capture_selector())):
        devices = await DeviceInformation.find_all_async_aqs_filter(selector)
        result[kind] = [dict(id=d.id, name=d.name, enabled=d.is_enabled) for d in devices]
    return result


def output_devices(sd):
    hosts = sd.query_hostapis()
    return [dict(index=i, name=d["name"], hostapi=hosts[d["hostapi"]]["name"],
                 max_output_channels=d["max_output_channels"],
                 default_samplerate=d["default_samplerate"])
            for i, d in enumerate(sd.query_devices()) if d["max_output_channels"] > 0]


def select_output(devices, name, channels):
    device = exact_match([d for d in devices if d["hostapi"] == "Windows WASAPI"], "name", name)
    if device["max_output_channels"] < channels:
        raise ProbeError("Selected output does not support requested channel count.")
    return device


def play_diagnostic(sd, data, name, rate, channels, volume, allow_unverified_route, purpose):
    if purpose != "message":
        raise ProbeError("Previews disabled: endpoint identity and capture isolation are unverified.")
    if not allow_unverified_route:
        raise ProbeError("Diagnostic playback requires --allow-unverified-route; use only nonprivate test audio.")
    pcm = convert_pcm(data, rate, channels, volume)
    device = select_output(output_devices(sd), name, channels)
    settings = sd.WasapiSettings(exclusive=False, auto_convert=False)
    kwargs = dict(device=device["index"], samplerate=rate, channels=channels,
                  dtype="int16", extra_settings=settings)
    sd.check_output_settings(**kwargs)
    # Never retry, choose a default, or switch devices after a failure.
    if select_output(output_devices(sd), name, channels) != device:
        raise ProbeError("Output inventory changed. Rerun and explicitly select again.")
    with sd.RawOutputStream(**kwargs) as stream:
        if stream.write(pcm):
            raise ProbeError("Playback underflow; diagnostic did not pass.")
    return dict(output=device, sample_rate=rate, channels=channels, volume=volume,
                frames=len(pcm) // (2 * channels), stable_identity_verified=False,
                preview_enabled=False)


def piper_synthesize(model):
    from piper import PiperVoice
    model = Path(model)
    if not model.is_file() or not Path(str(model) + ".json").is_file():
        raise ProbeError("Provide an existing .onnx and matching .onnx.json pair.")
    voice = PiperVoice.load(str(model), use_cuda=False)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        voice.synthesize_wav(PHRASE, wav)
    return output.getvalue()


def save_wav(data, destination):
    info = wav_info(data)
    # Exclusive creation avoids accidentally replacing an existing recording.
    with Path(destination).open("xb") as output:
        output.write(data)
    return dict(wav=str(destination), **info)


def smoke():
    """Exercise packaged imports/native loading, no devices, models or speech required."""
    import sounddevice as sd
    import onnxruntime
    from piper import PiperVoice
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    from winrt.windows.storage.streams import DataReader
    from winrt.windows.devices.enumeration import DeviceInformation
    from winrt.windows.media.devices import MediaDevice
    import winrt.windows.foundation.collections
    return dict(portaudio=sd.get_portaudio_version(), onnxruntime=onnxruntime.__version__,
                imports="ok", frozen=bool(getattr(sys, "frozen", False)),
                python=platform.python_version(), windows=platform.platform(),
                synthesis="not tested", hardware="not tested")


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--report", type=Path, help="Write JSON diagnostics (also works in a windowed frozen executable)")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("smoke", help="Load packaged native dependencies; no playback")
    sub.add_parser("voices", help="Enumerate installed WinRT voices with exact IDs")
    sub.add_parser("endpoints", help="Report Windows endpoint IDs and separate PortAudio inventory")
    synth = sub.add_parser("synthesize", help="WinRT fixed phrase to WAV, no playback")
    synth.add_argument("--voice-id", required=True)
    synth.add_argument("--wav", required=True, type=Path)
    piper = sub.add_parser("piper", help="Piper API fixed phrase to WAV, no subprocess or downloads")
    piper.add_argument("--model", required=True, type=Path)
    piper.add_argument("--wav", required=True, type=Path)
    play = sub.add_parser("play", help="Explicit diagnostic WASAPI playback; never private previews")
    play.add_argument("--wav", required=True, type=Path)
    play.add_argument("--device-name", required=True)
    play.add_argument("--rate", type=int, choices=(44100, 48000), required=True)
    play.add_argument("--channels", type=int, choices=(1, 2), required=True)
    play.add_argument("--volume", type=float, default=0.2)
    play.add_argument("--purpose", choices=("message", "preview"), default="message")
    play.add_argument("--allow-unverified-route", action="store_true")
    stable = sub.add_parser("play-id", help="Diagnostic message playback through exact WASAPI endpoint ID")
    stable.add_argument("--wav", required=True, type=Path)
    stable.add_argument("--endpoint-id", required=True)
    stable.add_argument("--rate", type=int, choices=(44100, 48000), required=True)
    stable.add_argument("--volume", type=float, default=0.2)
    stable.add_argument("--allow-unverified-route", action="store_true")
    return root


def emit_report(payload, args, *, error=False):
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    target = sys.stderr if error else sys.stdout
    if target:
        print(json.dumps(payload, indent=2), file=target)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if sys.platform != "win32":
            raise ProbeError("Windows runtime required; portable tests can run on Linux.")
        if args.command == "smoke":
            result = smoke()
        elif args.command == "voices":
            result = dict(voices=winrt_voices())
        elif args.command == "synthesize":
            result = save_wav(asyncio.run(winrt_synthesize(args.voice_id)), args.wav)
        elif args.command == "piper":
            result = save_wav(piper_synthesize(args.model), args.wav)
        elif args.command == "endpoints":
            import sounddevice as sd
            from .windows_audio import endpoints
            from dataclasses import asdict
            result = dict(windows=asyncio.run(windows_endpoints()), portaudio=output_devices(sd),
                          wasapi=[asdict(d) for d in endpoints()],
                          portaudio_version=sd.get_portaudio_version(),
                          endpoint_id_mapping="unverified; names are not an identity join",
                          preview_enabled=False)
        elif args.command == "play-id":
            if not args.allow_unverified_route:
                raise ProbeError("Use --allow-unverified-route only for nonprivate test audio.")
            from .windows_audio import WindowsRouter
            from .windows_runtime import WindowsConfig
            import threading
            config = WindowsConfig(message_endpoint_id=args.endpoint_id,
                                   output_rate=args.rate, speech_volume=args.volume * 100)
            WindowsRouter().play(args.wav.read_bytes(), config, False, None, threading.Event())
            result = dict(endpoint_id=args.endpoint_id, sample_rate=args.rate,
                          volume=args.volume, hardware_isolation_verified=False)
        else:
            import sounddevice as sd
            result = play_diagnostic(sd, args.wav.read_bytes(), args.device_name, args.rate,
                                     args.channels, args.volume, args.allow_unverified_route, args.purpose)
        emit_report(dict(ok=True, command=args.command, result=result), args)
        return 0
    except Exception as exc:
        # No arbitrary exception text: native exceptions can contain input or paths.
        error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
        emit_report(dict(ok=False, command=args.command, error=error,
                         winerror=getattr(exc, "winerror", None)), args, error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
