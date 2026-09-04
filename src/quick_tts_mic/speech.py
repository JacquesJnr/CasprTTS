from __future__ import annotations

import queue
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .audio import PipeWireRouter
from .config import AppConfig


class SpeechError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SpeechRequest:
    text: str
    submitted_at: float


class PiperEngine:
    def synthesize(self, text: str, model_path: str, output_path: str) -> None:
        model = Path(model_path).expanduser()
        if not model.is_file():
            raise SpeechError("Choose a Piper .onnx voice model in Settings")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "piper",
                "--model",
                str(model),
                "--output_file",
                output_path,
            ],
            input=text,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise SpeechError(result.stderr.strip() or "Piper synthesis failed")


class SpeechQueue:
    def __init__(
        self,
        config_provider: Callable[[], AppConfig],
        error_callback: Callable[[str], None],
        router: PipeWireRouter | None = None,
        engine: PiperEngine | None = None,
    ) -> None:
        self._config_provider = config_provider
        self._error_callback = error_callback
        self._router = router or PipeWireRouter()
        self._engine = engine or PiperEngine()
        self._queue: queue.Queue[SpeechRequest | None] = queue.Queue()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    @property
    def router(self) -> PipeWireRouter:
        return self._router

    def submit(self, text: str) -> None:
        self._queue.put(SpeechRequest(text=text, submitted_at=time.monotonic()))

    def stop(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=3)
        self._router.close()

    def _work(self) -> None:
        while True:
            request = self._queue.get()
            if request is None:
                return
            config = self._config_provider()
            try:
                with tempfile.TemporaryDirectory(prefix="quick-tts-") as temp_dir:
                    wav_path = str(Path(temp_dir) / "speech.wav")
                    self._engine.synthesize(request.text, config.model_path, wav_path)
                    remaining = (
                        request.submitted_at
                        + max(0.0, config.playback_delay_seconds)
                        - time.monotonic()
                    )
                    if remaining > 0:
                        time.sleep(remaining)
                    self._router.play(
                        wav_path,
                        monitor_locally=config.local_monitor,
                        local_output=config.local_output,
                    )
            except Exception as error:  # Keep the queue alive after a failed item.
                self._error_callback(str(error))
