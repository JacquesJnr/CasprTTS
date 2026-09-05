from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass


VIRTUAL_SINK = "quick_tts_sink"
VIRTUAL_SOURCE = "quick_tts_mic"
PLAYBACK_PREROLL_SECONDS = 0.5


def _write_prerolled_wav(source_path: str, output_path: str) -> None:
    """Wake the output in the same stream that will carry the speech."""
    with wave.open(source_path, "rb") as source:
        with wave.open(output_path, "wb") as output:
            output.setparams(source.getparams())
            frames = round(source.getframerate() * PLAYBACK_PREROLL_SECONDS)
            # Unsigned 8-bit PCM has its silence midpoint at 128.
            silence = b"\x80" if source.getsampwidth() == 1 else b"\x00"
            output.writeframes(
                silence * frames * source.getnchannels() * source.getsampwidth()
            )
            while chunk := source.readframes(65536):
                output.writeframes(chunk)


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
        self._lock = threading.Lock()

    @property
    def discord_source_name(self) -> str:
        return VIRTUAL_SOURCE

    def ensure_virtual_mic(self) -> None:
        with self._lock:
            sink_module_ids = self._module_ids(
                "module-null-sink", f"sink_name={VIRTUAL_SINK}"
            )
            if sink_module_ids:
                # Old prototype processes can leave server-side Pulse modules
                # behind. Keep one canonical device and remove duplicates.
                for module_id in sink_module_ids[1:]:
                    self._unload(module_id)
            else:
                self._load_module(
                    "module-null-sink",
                    f"sink_name={VIRTUAL_SINK}",
                    "sink_properties=device.description=QuickTTS_Microphone_Output",
                )

            source_module_ids = self._module_ids(
                "module-remap-source", f"source_name={VIRTUAL_SOURCE}"
            )
            if source_module_ids:
                for module_id in source_module_ids[1:]:
                    self._unload(module_id)
            else:
                self._load_module(
                    "module-remap-source",
                    f"master={VIRTUAL_SINK}.monitor",
                    f"source_name={VIRTUAL_SOURCE}",
                    "source_properties=device.description=QuickTTS_Microphone device.class=sound",
                )

    def close(self) -> None:
        with self._lock:
            # The remapped source depends on the null sink, so unload it first.
            for module_id in self._module_ids(
                "module-remap-source", f"source_name={VIRTUAL_SOURCE}"
            ):
                self._unload(module_id)
            for module_id in self._module_ids(
                "module-null-sink", f"sink_name={VIRTUAL_SINK}"
            ):
                self._unload(module_id)

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

    def play(
        self, wav_path: str, monitor_locally: bool, local_output: str = "",
        volume: int = 100,
    ) -> None:
        self.ensure_virtual_mic()
        with tempfile.TemporaryDirectory(prefix="quick-tts-playback-") as temp_dir:
            playback_path = f"{temp_dir}/speech.wav"
            _write_prerolled_wav(wav_path, playback_path)
            self._play_file(playback_path, monitor_locally, local_output, volume)

    def play_sample(self, wav_path: str, local_output: str = "", volume: int = 100) -> None:
        # Resolve an explicit non-Caspr sink even when the system default is
        # the virtual mic. Never fall back to paplay's implicit default here.
        outputs = self.outputs()
        names = {output.name for output in outputs}
        if local_output:
            target = local_output if local_output in names else ""
        else:
            result = subprocess.run(
                ["pactl", "get-default-sink"], text=True, capture_output=True,
            )
            default = result.stdout.strip() if result.returncode == 0 else ""
            target = default if default in names else (outputs[0].name if outputs else "")
        if not target:
            raise AudioError("Choose an available headphone output to sample a voice")
        with tempfile.TemporaryDirectory(prefix="quick-tts-sample-") as temp_dir:
            playback_path = f"{temp_dir}/sample.wav"
            _write_prerolled_wav(wav_path, playback_path)
            volume_arg = f"--volume={round(max(0, min(100, volume)) * 65536 / 100)}"
            result = subprocess.run(["paplay", volume_arg, "--device", target, playback_path])
            if result.returncode:
                raise AudioError("Voice sample playback failed")

    def _play_file(
        self, wav_path: str, monitor_locally: bool, local_output: str,
        volume: int = 100,
    ) -> None:
        # PipeWire's PulseAudio compatibility layer gives us stable device
        # names. Native pw-play targets are numeric node IDs on this system and
        # change whenever the virtual sink is recreated.
        volume_arg = f"--volume={round(max(0, min(100, volume)) * 65536 / 100)}"
        commands = [["paplay", volume_arg, "--device", VIRTUAL_SINK, wav_path]]
        if monitor_locally:
            command = ["paplay", volume_arg]
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

    def _module_ids(self, module_name: str, marker: str) -> list[str]:
        result = subprocess.run(
            ["pactl", "list", "short", "modules"],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            return []
        return [
            line.split("\t", 1)[0]
            for line in result.stdout.splitlines()
            if module_name in line and marker in line
        ]

    @staticmethod
    def _load_module(module_name: str, *arguments: str) -> str:
        result = subprocess.run(
            ["pactl", "load-module", module_name, *arguments],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise AudioError(result.stderr.strip() or "Could not create virtual microphone")
        return result.stdout.strip()

    @staticmethod
    def _unload(module_id: str) -> None:
        subprocess.run(
            ["pactl", "unload-module", module_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
