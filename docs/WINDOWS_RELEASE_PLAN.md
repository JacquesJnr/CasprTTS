# Caspr TTS Windows release plan

Updated 2026-11-03. Branch: `feature/windows-webview`. Target: a friend's Windows 10
x64 PC. Nothing here has run on Windows yet; Linux tests are not Windows validation.

## Stack

One UI for both platforms: the React/Watermelon pages in `web/`, shown by
**pywebview**. On Windows that is WinForms + **Microsoft Edge WebView2** through
pythonnet (.NET Framework 4.x ships with Windows 10). `web_app.py` picks a backend by
platform:

| | Linux | Windows |
| --- | --- | --- |
| Config | `AppConfig` (`~/.config/quick-tts-mic`) | `WindowsConfig` (`%LOCALAPPDATA%\Caspr TTS`, migrates the Linux-style file) |
| Speech | `SpeechQueue`: Piper | `WindowsSpeechQueue`: Piper or Microsoft (WinRT) |
| Output | PipeWire virtual mic `quick_tts_mic` | WASAPI to an exact device ID; Discord records **Stereo Mix** |
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
4. **First release unsigned.** SmartScreen → *More info → Run anyway* is acceptable.

Samples ("Sample voice") play only on a headphone output that differs from the
message output, so they never reach Stereo Mix. This replaces the old per-session
"verify preview isolation" checkbox.

## Done on this branch

- Windows backend merged under the new UI; Windows Settings shows a Microsoft/Piper
  switch (Microsoft voices with flag + ♂/♀), message and headphone output pickers,
  an editable hotkey and **Open voices folder**. Linux Settings is unchanged.
- Overlay voice switcher lists Microsoft voices when that provider is selected.
- Flag emoji render on Windows via a bundled Twemoji country-flag font (no CDN).
- Global hotkey, tray, frozen-path handling (`sys._MEIPASS/web/dist`).
- Packaging: spec/launcher for pywebview, smoke test covering every native piece,
  installer runs Microsoft's (signature-checked) WebView2 bootstrapper when missing,
  CI builds the UI with Node 22, regenerated hash-locked Windows dependencies.

## Next steps and exit gates

| Step | Work | Exit gate |
| --- | --- | --- |
| 1. CI build | Push the branch; fix whatever the first `windows-2022` run finds | Tests, frozen smoke, installer install/upgrade/uninstall all green; installer artifact produced |
| 2. Probe on the target PC | Run `CasprTTS.exe --probe` and `scripts/windows-sapi-probe.ps1` from the artifact | Know whether James is exposed via WinRT (needed) or only SAPI; Realtek endpoint ID and Stereo Mix confirmed; WebView2 present or installed |
| 3. App on the target PC | Install, pick James + Realtek, Discord input = Stereo Mix | Overlay transparent/on top and focused by Ctrl+Alt+T; tray works; speech audible in a recorded Discord call; samples absent from that recording |
| 4. Acceptance | Checklist below | All items pass, then tag `windows-v0.1.0` to publish an unsigned prerelease |

Acceptance checklist: first install (with and without WebView2), James present and
absent, Piper model added later, monitoring on/off, 0/100% volume, rapid sends and a
synthesis failure, Realtek unplug/replug, duplicate device names, sleep/resume,
default-output change, hotkey conflict, second launch, 100/150/200% scaling,
non-ASCII user name/path, upgrade and uninstall.

## Open risks

- **James via WinRT.** If James is only a SAPI voice, the WinRT provider can't use it;
  options are a SAPI adapter or a different Microsoft voice.
- **Transparent frameless overlay on WebView2** is untested; fallback is an opaque
  rounded window.
- **First-build packaging** (pythonnet/WebView2 collection, proxy_tools source build)
  is unverified until CI runs.
- **Licensing review** before a public release: Piper (GPL-3.0-or-later), pystray
  (LGPL-3.0), WebView2 SDK DLLs, Twemoji flags (CC-BY 4.0), bundled npm packages.
