from __future__ import annotations

import json
import subprocess
import threading
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
        self._lock = threading.Lock()

    @property
    def discord_source_name(self) -> str:
        return f"{VIRTUAL_SINK}.monitor"

    def ensure_virtual_mic(self) -> None:
        with self._lock:
            module_ids = self._module_ids()
            if module_ids:
                # Old prototype processes can leave server-side Pulse modules
                # behind. Keep one canonical device and remove duplicates.
                for module_id in module_ids[1:]:
                    self._unload(module_id)
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
        with self._lock:
            for module_id in self._module_ids():
                self._unload(module_id)
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
        # PipeWire's PulseAudio compatibility layer gives us stable device
        # names. Native pw-play targets are numeric node IDs on this system and
        # change whenever the virtual sink is recreated.
        commands = [["paplay", "--device", VIRTUAL_SINK, wav_path]]
        if monitor_locally:
            command = ["paplay"]
            if local_output:
                command += ["--device", local_output]
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

    def _module_ids(self) -> list[str]:
        result = subprocess.run(
            ["pactl", "list", "short", "modules"],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            return []
        marker = f"sink_name={VIRTUAL_SINK}"
        return [
            line.split("\t", 1)[0]
            for line in result.stdout.splitlines()
            if "module-null-sink" in line and marker in line
        ]

    @staticmethod
    def _unload(module_id: str) -> None:
        subprocess.run(
            ["pactl", "unload-module", module_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
