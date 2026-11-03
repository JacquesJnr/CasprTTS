# Windows speech and routing probes

The probes are diagnostic tools separate from the app itself. They do not
change application preferences, Windows default devices, voice registrations or
Discord settings. Synthesis uses a fixed nonprivate phrase and writes an explicitly
requested WAV; delete that WAV when finished. No Microsoft voices or Piper models
are downloaded by these commands.

Use Windows 10/11 x64 with Python 3.11 and the pinned environment described in
[WINDOWS_BUILD.md](WINDOWS_BUILD.md). From the repository, install the package
editable after the Windows requirements, then use PowerShell:

```powershell
python -m quick_tts_mic.windows_probe --report voices.json voices
python -m quick_tts_mic.windows_probe --report endpoints.json endpoints
```

JSON `ok` and the process exit code describe command success. An empty voice or
endpoint list is valid enumeration, **not** a synthesis/hardware pass. Native errors
report their class and Windows error number without arbitrary exception messages.
The optional `--report` goes **before** the subcommand. It is required to see output
when invoking the windowed bundle:

```powershell
$p = Start-Process .\CasprTTS.exe -ArgumentList '--probe --report voices.json voices' -Wait -PassThru
$p.ExitCode
Get-Content voices.json
```

Use `Start-Process -Wait` for frozen probes because the executable is a GUI process.
For paths/IDs containing spaces, PowerShell's argument string must include quotes.

## Installed voices and WAV synthesis

Copy an exact `id` returned by `voices` (display names are not identity):

```powershell
python -m quick_tts_mic.windows_probe synthesize --voice-id 'EXACT ID FROM JSON' --wav winrt.wav
python -m quick_tts_mic.windows_probe piper --model 'C:\Voices\voice.onnx' --wav piper.wav
```

A missing or duplicate exact voice ID fails; no default voice is substituted. WAV
reports include duration, frame count, sample rate, width and channels. Output files
must not already exist. The Piper command calls `PiperVoice` inside the current
process, including when frozen; it never treats the executable as a Python interpreter.
Run the same Piper probe from the directory bundle on a clean Windows machine with
no Python/developer tools, using your own licensed `.onnx` / `.onnx.json` pair.

If James is absent from WinRT, use the separate SAPI diagnostic:

```powershell
powershell -NoProfile -File scripts\windows-sapi-probe.ps1
powershell -NoProfile -File scripts\windows-sapi-probe.ps1 -VoiceId 'EXACT SAPI ID' -Wav sapi.wav
```

SAPI synthesis writes a file stream; it does not speak to the default output. SAPI
is diagnostic only and is not a selectable app provider. Record James as present,
absent, synthesis failed, or audible/verified for **each** API. Do not patch registry
entries or copy voice resources to make James appear.

## Output identity and playback

`endpoints` reports Windows render/capture IDs, the PortAudio output inventory, and
the `wasapi` outputs the app offers. The app plays through PortAudio's WASAPI host API
in shared mode with `auto_convert`, so Windows adapts mono/stereo speech to the
device's channel count, rate and sample format. Outputs are saved by exact WASAPI
device name (PortAudio indexes change between runs); a duplicated name is reported as
ambiguous and never guessed.

For the application's endpoint-ID path:

```powershell
python -m quick_tts_mic.windows_probe play-id --wav winrt.wav --endpoint-id 'EXACT wasapi ID' --rate 48000 --volume 0.2 --allow-unverified-route
python -m quick_tts_mic.windows_probe play-id --wav piper.wav --endpoint-id 'EXACT wasapi ID' --rate 44100 --volume 0.2 --allow-unverified-route
```

This is deliberately audible test playback; use nonprivate audio. No microphone is
created. A missing selected output fails without replacement. The app adapter uses
polyphase resampling, mono/stereo conversion, volume, and a 0.5-second silent lead-in.
The output's WASAPI shared mode handles the final device format negotiation.

For comparison, the original PortAudio feasibility path remains available:

```powershell
python -m quick_tts_mic.windows_probe play --wav winrt.wav --device-name 'Exact unique WASAPI name' --rate 48000 --channels 2 --volume 0.2 --allow-unverified-route
```

It refuses duplicate names, non-WASAPI devices, unsupported formats and preview
requests. It never retries a default. Its linear resampler is diagnostic only;
PortAudio enumeration can cache device state, so restart the probe after device
changes. This path does not establish stable identity or private preview safety.

## What must be measured on Windows

Record OS build, artifact SHA-256, voice IDs/locales, output IDs and device/driver
versions alongside each result. Native imports and CI freezing alone do not prove:

- James availability and intelligible synthesis on the original user's machine.
- Piper synthesis from the frozen bundle with no installed Python.
- Realtek Stereo Mix capture of the selected message output; actual Discord PTT.
- Optional cable playback to CABLE Input and capture from CABLE Output.
- Preview absence from a recorded Discord capture stream with the chosen mixer setup.
- Unplug/replug, duplicate names, default-device changes, sleep/resume and stream failures.
- Audible completeness at 44.1/48 kHz, mono/stereo and 0/100% volume with both providers.

Private previews in the app require a separate output and a per-session user
verification. That acknowledgement records the user's external capture test, not an
automated proof. Revoking it, changing outputs, detected device/power changes or
restart disables previews; queued previews also lose authorization. External mixer
changes cannot all be detected, so recheck isolation after changing them.

## Linux verification

Portable tests import no Windows speech/audio libraries unless executing a native
operation. Existing Linux tests remain runnable with only the development requirements:

```bash
python -m pytest -q
```

For conversion coverage, install NumPy and SciPy in an isolated environment and run
the same command. Those dependency-specific tests skip if their packages are absent. Windows CI installs
the pinned packages, so they run there. Portable tests cover exact/missing/duplicate
selection, no fallback, preview revocation, PCM conversion, config preservation,
queue recovery/cancellation and settings validation. They simulate devices and
voices; they do not validate hardware, WinRT, SAPI or an installer.

References used for the adapters:
[PyWinRT projection conventions](https://pywinrt.readthedocs.io/en/latest/types.html),
[SoundCard WASAPI implementation](https://github.com/bastibe/SoundCard/blob/0.4.6/soundcard/mediafoundation.py),
[Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/v1.4.2/src/piper/voice.py),
[PortAudio stream API](https://python-sounddevice.readthedocs.io/en/0.5.1/api/streams.html).
