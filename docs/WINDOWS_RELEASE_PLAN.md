# Caspr TTS Windows release plan

Updated 2026-11-04. Branch: `feature/windows-webview`. Target: a friend's Windows 10
x64 PC; tested on a Windows 11 x64 PC (see Status).

## Stack

One UI for both platforms: the React/Watermelon pages in `web/`, shown by
**pywebview**. On Windows that is WinForms + **Microsoft Edge WebView2** through
pythonnet (.NET Framework 4.x ships with Windows 10). `web_app.py` picks a backend by
platform:

| | Linux | Windows |
| --- | --- | --- |
| Config | `AppConfig` (`~/.config/quick-tts-mic`) | `WindowsConfig` (`%LOCALAPPDATA%\Caspr TTS`, migrates the Linux-style file) |
| Speech | `SpeechQueue`: Piper | `WindowsSpeechQueue`: Piper or Microsoft (WinRT) |
| Output | PipeWire virtual mic `quick_tts_mic` | PortAudio WASAPI (shared, `auto_convert`) to an exact device name; Discord records **Stereo Mix** |
| Shortcut | Desktop/WM binding → `scripts/quick-tts-overlay` | `RegisterHotKey` thread (`windows_shell.py`), default Ctrl+Alt+T |
| Background | Hidden overlay keeps the process alive | Same, plus a **pystray** tray icon |
| Single instance | Unix socket | Named pipe (same `multiprocessing.connection` code) |

The earlier Qt shell (`windows_ui.py` on `feature/windows-release`) is retired; its
backend (`windows_runtime.py`, `windows_audio.py`, `windows_probe.py`), probes,
PyInstaller/Inno packaging and CI were brought over.

## Decisions (2026-11-03)

1. **Audio route: Stereo Mix.** Message output is the Realtek device Stereo Mix
   records; Discord's input is Stereo Mix. Accepted trade-off: Discord also hears
   everything else on that output. VB-CABLE stays possible but is not the default.
2. **Default voice: Microsoft James** when Windows exposes it; Piper optional.
3. **Tray icon via pystray** (Open message box / Settings / Quit).
4. **Releases stay unsigned** (decided 2026-11-04: not worth a certificate for one user).
   SmartScreen → *More info → Run anyway*. `build.ps1` can still sign with a certificate
   thumbprint if that changes.
5. **License: GPL-3.0-or-later** (`LICENSE.md`), required by the bundled Piper engine.

Samples ("Sample voice") play only on a headphone output that differs from the
message output, so they never reach Stereo Mix. This replaces the old per-session
"verify preview isolation" checkbox.

## Status (2026-11-04)

Tested on the target Windows 11 PC with build `dev.16`: Settings and the overlay render,
outputs list the Realtek device, Microsoft voices (including James, installed via Windows
speech settings and exposed through WinRT) and Piper voices both speak, and only Settings
appears at launch.

Fixed along the way (each now covered by the CI smoke test where possible):
- PyInstaller's `pkg_resources` hook crashed before startup (setuptools 80); excluded.
- WebView2 blocks ES modules on `file://`; the UI is served from pywebview's localhost server.
- Each UI data source is read separately so one failure can't blank a window.
- Playback moved from SoundCard to sounddevice/PortAudio WASAPI with `auto_convert`
  (SoundCard failed with E_INVALIDARG on the Realtek SST speakers; it can't ask Windows to
  convert formats, likely a channel-count mismatch); SciPy is no longer
  bundled because Windows resamples.
- The Visual C++ runtime is bundled and preloaded so onnxruntime (Piper) loads on PCs
  without a current system copy.
- The overlay is opaque on Windows (pywebview can't make WinForms windows transparent),
  fits its content, grows upward for menus, stays hidden at launch, remembers its
  position, and Windows 11 rounds its corners.
- First-message latency: warm-up at launch and one reused SpeechSynthesizer.

## Release

Merge `feature/windows-webview` into `main`, then push a `windows-v0.1.0` tag: CI builds,
runs the smoke and installer checks, and publishes an unsigned GitHub prerelease with
SHA-256 checksums. Add required reviewers to the `windows-release` environment first.

Remaining manual checks before calling it 1.0: Discord over Stereo Mix in a recorded call,
hotkey conflict, Realtek unplug/replug, sleep/resume, 150/200% scaling, a non-ASCII
Windows user name, and upgrade/uninstall on the PC.
