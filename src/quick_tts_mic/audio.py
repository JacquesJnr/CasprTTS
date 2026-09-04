from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


VIRTUAL_SINK = "quick_tts_sink"


class AudioError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AudioOutput:
    name: str
    description: str


class PipeWireRouter:
    """Creates a PulseAudio-compatible null sink backed by PipeWire.

    Discord records the sink's monitor source. Generated audio is played into
    the sink and, optionally, to the user's normal output at the same time.
    """

    def __init__(self) -> None:
        self._module_id: str | None = None

    @property
    def discord_source_name(self) -> str:
        return f"{VIRTUAL_SINK}.monitor"

    def ensure_virtual_mic(self) -> None:
        if self._sink_exists():
            return
        result = subprocess.run(
            [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={VIRTUAL_SINK}",
                "sink_properties=device.description=QuickTTS_Microphone",
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise AudioError(result.stderr.strip() or "Could not create virtual microphone")
        self._module_id = result.stdout.strip()

    def close(self) -> None:
        if self._module_id:
            subprocess.run(
                ["pactl", "unload-module", self._module_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._module_id = None

    def outputs(self) -> list[AudioOutput]:
        result = subprocess.run(
            ["pactl", "-f", "json", "list", "sinks"],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            return []
        try:
            sinks = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        return [
            AudioOutput(sink["name"], sink.get("description", sink["name"]))
            for sink in sinks
            if sink.get("name") != VIRTUAL_SINK
        ]

    def play(self, wav_path: str, monitor_locally: bool, local_output: str = "") -> None:
        self.ensure_virtual_mic()
        commands = [["pw-play", "--target", VIRTUAL_SINK, wav_path]]
        if monitor_locally:
            command = ["pw-play"]
            if local_output:
                command += ["--target", local_output]
            commands.append(command + [wav_path])

        processes = [subprocess.Popen(command) for command in commands]
        failures = [process.wait() for process in processes]
        if any(failures):
            raise AudioError("Audio playback failed")

    def _sink_exists(self) -> bool:
        result = subprocess.run(
            ["pactl", "get-sink-info", VIRTUAL_SINK],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0

