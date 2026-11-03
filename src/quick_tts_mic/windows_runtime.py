"""Windows state and FIFO speech worker, independent of either GUI toolkit."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
import io
import json
import math
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import wave

from .config import AppConfig, normalize_quick_options
from .voices import KNOWN_VOICES, VoiceOption
from .windows_probe import ProbeError, wav_info, winrt_synthesize


def data_dir():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Caspr TTS"


def config_path():
    return data_dir() / "config.json"


def voice_dir():
    return data_dir() / "data" / "voices"


@dataclass(slots=True)
class WindowsConfig(AppConfig):
    model_path: str = ""
    local_monitor: bool = False
    debug_notifications: bool = False
    speech_provider: str = "piper"
    message_endpoint_id: str = ""
    preview_endpoint_id: str = ""
    output_rate: int = 48000
    hotkey: str = "Ctrl+Alt+T"
    _extra: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path=None):
        destination = config_path() if path is None else Path(path)
        path = destination
        legacy = Path.home() / ".config" / "quick-tts-mic" / "config.json"
        migrate = not destination.exists() and path == config_path() and legacy.is_file()
        if migrate:
            path = legacy
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(values, dict):
            return cls()
        default = cls()
        fields = cls.__dataclass_fields__
        clean = {}
        for key, value in values.items():
            if key not in fields or key == "_extra":
                continue
            expected = getattr(default, key)
            if key == "quick_options":
                clean[key] = normalize_quick_options(value)
                continue
            if isinstance(expected, bool):
                valid = isinstance(value, bool)
            elif isinstance(expected, (int, float)):
                valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            else:
                valid = isinstance(value, str)
            if valid:
                clean[key] = value
        result = cls(**clean)
        result.speech_volume = int(max(0, min(100, result.speech_volume)))
        result.playback_delay_seconds = max(0, min(30, result.playback_delay_seconds))
        result.history_limit = 25
        if result.speech_provider not in ("piper", "microsoft"):
            result.speech_provider = "piper"
        if result.output_rate not in (44100, 48000):
            result.output_rate = 48000
        result._extra = {k: v for k, v in values.items() if k not in fields}
        if migrate:
            result.save(destination)
        return result

    def save(self, path=None):
        path = Path(path) if path is not None else config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        values = asdict(self)
        values.pop("_extra")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({**self._extra, **values}, indent=2) + "\n", encoding="utf-8")
        for attempt in range(5):
            try:
                temporary.replace(path)
                return
            except PermissionError:  # another process briefly holds config.json open
                if attempt == 4:
                    raise
                time.sleep(0.05)


def discover_windows_models(current="", directory=None):
    directory = Path(directory) if directory is not None else voice_dir()
    models = sorted(directory.glob("*.onnx"))
    if current and Path(current).expanduser() not in models:
        models.append(Path(current).expanduser())
    voices = []
    for model in models:
        if model.is_file() and Path(str(model) + ".json").is_file():
            name, detail, gender = KNOWN_VOICES.get(model.stem, (model.stem, "Custom Piper voice", ""))
            voices.append(VoiceOption(name=name, detail=detail, model_path=str(model), gender=gender))
    return voices


def parse_hotkey(value):
    parts = [part.strip().upper() for part in value.split("+")]
    if len(parts) < 2 or len(set(parts)) != len(parts):
        raise ProbeError("Use Ctrl/Alt/Shift plus a letter, digit or F1–F24, for example Ctrl+Alt+T.")
    modifiers = {"ALT": 1, "CTRL": 2, "SHIFT": 4}
    if any(part not in modifiers for part in parts[:-1]):
        raise ProbeError("Hotkey modifiers must be Ctrl, Alt or Shift.")
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        code = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        code = 0x70 + int(key[1:]) - 1
    else:
        raise ProbeError("Hotkey must end in a letter, digit or F1–F24.")
    return sum(modifiers[part] for part in parts[:-1]) | 0x4000, code


@contextmanager
def com_apartment():
    """Each worker initializes its own COM apartment, including SoundCard calls."""
    if sys.platform != "win32":
        yield
        return
    import ctypes
    ole = ctypes.OleDLL("ole32")
    result = ole.CoInitializeEx(None, 0)
    if result not in (0, 1):
        raise ProbeError("Could not initialize Windows audio worker.")
    try:
        yield
    finally:
        ole.CoUninitialize()


class SpeechEngine:
    def __init__(self):
        self._model_path = None
        self._voice = None

    def synthesize(self, text, config):
        if config.speech_provider == "microsoft":
            return asyncio.run(winrt_synthesize(config.microsoft_voice_id, text))
        if config.speech_provider != "piper":
            raise ProbeError("Select a supported speech provider.")
        model = Path(config.model_path).expanduser()
        if not model.is_file() or not Path(str(model) + ".json").is_file():
            raise ProbeError("Choose a Piper .onnx voice with its matching .onnx.json file.")
        if self._model_path != str(model):
            from piper import PiperVoice
            self._voice = PiperVoice.load(str(model), use_cuda=False)
            self._model_path = str(model)
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            self._voice.synthesize_wav(text, wav)
        return output.getvalue()


@dataclass(frozen=True)
class Request:
    text: str
    config: WindowsConfig
    submitted: float
    preview: bool = False
    preview_verification: tuple | None = None
    on_complete: object = None


class WindowsSpeechQueue:
    def __init__(self, error_callback, status_callback=lambda _: None, engine=None, router=None):
        if router is None:
            from .windows_audio import WindowsRouter
            router = WindowsRouter()
        self.router = router
        self.engine = engine or SpeechEngine()
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.pending = queue.Queue()
        self.cancelled = threading.Event()
        self.thread = threading.Thread(target=self._work, daemon=True, name="Caspr speech")
        self.thread.start()

    def submit(self, text, config, *, preview=False, preview_verification=None, on_complete=None):
        if not text.strip() or self.cancelled.is_set():
            return
        self.pending.put(Request(text.strip(), replace(config), time.monotonic(), preview,
                                 preview_verification, on_complete))

    def stop(self):
        self.cancelled.set()
        self.pending.put(None)
        self.thread.join(timeout=3)

    def _work(self):
        try:
            with com_apartment():
                self._consume()
        except Exception:
            self.error_callback("Windows speech worker could not start. Restart Caspr TTS.")

    def _consume(self):
        while not self.cancelled.is_set():
            request = self.pending.get()
            if request is None:
                return
            stage = "output check"
            try:
                self.status_callback("Synthesizing…")
                # Validate before synthesizing as well as immediately before playback.
                self.router.validate(request.config, request.preview, request.preview_verification)
                stage = f"{request.config.speech_provider} synthesis"
                data = self.engine.synthesize(request.text, request.config)
                wav_info(data)
                remaining = 0 if request.preview else max(0, request.submitted +
                    request.config.playback_delay_seconds - time.monotonic())
                if self.cancelled.wait(remaining):
                    return
                stage = "playback"
                self.status_callback("Playing…")
                self.router.play(data, request.config, request.preview, request.preview_verification, self.cancelled)
            except Exception as error:
                if isinstance(error, ProbeError):
                    self.error_callback(str(error))
                else:
                    # Messages may contain the spoken text, which never leaves memory; the stage,
                    # type and stack frames (to caspr.log) are enough to locate the failure.
                    # Playback errors only describe audio devices (e.g. SoundCard's "Error 0x8889…"),
                    # so their message is shown; synthesis messages are not.
                    detail = f"{type(error).__name__}: {error}" if stage == "playback" else type(error).__name__
                    print(f"{stage} failed: {detail}\n" + "".join(traceback.format_tb(error.__traceback__)),
                          file=sys.stderr)
                    self.error_callback(f"{stage.capitalize()} failed ({detail}). Details are in caspr.log.")
            finally:
                self.status_callback("Ready")
                if request.on_complete:
                    request.on_complete()


SAMPLE_PHRASE = "I love text-to-speech"


class WindowsBackend:
    """Speech/output adapter the pywebview shell uses on Windows (Linux: speech.SpeechQueue)."""

    discord_input = "Stereo Mix"

    def __init__(self, config_provider, error_callback):
        from .windows_audio import WindowsRouter, soundcard
        # SoundCard calls CoInitializeEx at import and treats S_FALSE ("already initialised") as
        # fatal, leaving a half-imported module. Import it here, before any com_apartment() runs.
        soundcard()
        self._config = config_provider
        # ponytail: a preview is "verified" when its output differs from the message output
        # (Stereo Mix only captures the message device); add an explicit check if leaks show up.
        self.queue = WindowsSpeechQueue(error_callback, router=WindowsRouter(lambda token: token is not None))

    def prepare(self):
        pass  # Stereo Mix is a Windows device; nothing to create.

    def submit(self, text):
        self.queue.submit(text, self._config())

    def sample(self, on_complete):
        from .windows_audio import endpoints, topology
        config = self._config()
        with com_apartment():
            verification = (config.message_endpoint_id, config.preview_endpoint_id, topology(endpoints()))
        self.queue.submit(SAMPLE_PHRASE, config, preview=True,
                          preview_verification=verification, on_complete=on_complete)

    def stop(self):
        self.queue.stop()

    def outputs(self):
        from .windows_audio import endpoints
        with com_apartment():
            return [{"name": e.id, "description": e.name} for e in endpoints()]

    def voices(self, config):
        return discover_windows_models(config.model_path)
