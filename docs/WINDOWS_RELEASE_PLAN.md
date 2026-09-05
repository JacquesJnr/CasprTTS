# Caspr TTS Windows release plan

Research date: 2026-09-05. Branch: `feature/windows-release`.
Status: release proposal with a preliminary Microsoft voice preference picker;
no Windows backend or executable validated yet.

## Authorized preliminary voice preference picker

The separately authorized settings dropdown is now implemented in the current GTK
shell. It saves `microsoft_voice_id` independently of Piper's `model_path` and uses
PyWinRT `SpeechSynthesizer.all_voices` to enumerate installed voice IDs, display
names and languages. Install the optional discovery dependencies on Windows with
`pip install '.[windows-voices]'`. No voice names or IDs are bundled as options.
This uses the [PyWinRT property projection](https://pywinrt.readthedocs.io/en/latest/types.html#properties).

The picker is disabled on Linux/Omarchy, when dependencies are missing, when the
API fails, or when no voices are returned. An absent saved voice remains saved
with no automatic replacement. Discovery runs when settings are first built;
restart Caspr after installing/removing voices to refresh the list.

This is preference storage only: Microsoft playback and provider switching are
not implemented. Messages, samples and the overlay continue to use Piper. The
Windows Qt shell, audio backend, packaging and actual Windows API validation
remain release work. Tests on Linux cover the optional discovery boundary with
simulated API responses; they do not verify installed Windows voices or James.

## Recommended release

Keep the Python application core and build a Windows shell with **PySide6 / Qt
Widgets**. Use **PyWinRT** for installed Microsoft voices, **Piper** for local
ONNX voices, and **sounddevice / PortAudio / WASAPI** for explicit output routing.
Freeze a directory bundle with **PyInstaller**, then distribute it through an
**Inno Setup** per-user installer. Build and test the actual artifacts on Windows.
These are recommended choices, subject to the speech and audio probes below.

Preserve the requirements in `PROJECT_SPEC.md`: Windows 10, Microsoft James when
accessible, the user's existing Realtek Stereo Mix route, optional virtual cable
support, a configurable global shortcut, and a normal background/tray app.
Proposed first test targets are Windows 10 22H2 x64 and Windows 11 x64. Confirm
the original user's exact build before declaring the minimum; lock dependencies
to versions that pass both targets. Defer native ARM64 and 32-bit builds.

## What the repository needs

| Current implementation | Windows release work |
| --- | --- |
| `app.py`: GTK, Gio application lifecycle, GLib callbacks | New Qt shell, tray, native hotkey, and single-instance activation |
| `audio.py`: `pactl`, `paplay`, PipeWire virtual source | Windows playback adapter; use an existing recording route |
| `speech.py`: queue coupled to `PipeWireRouter` and `PiperEngine` | Inject speech and audio interfaces; preserve ordering, delay and samples |
| Piper invoked using `sys.executable -m piper` | Use Piper's Python API in a worker; a frozen executable is not a general Python interpreter |
| `voices.py`: identity is a model path | Provider + stable ID + locale + display name + optional model path |
| `config.py`: `~/.config` and repository-relative model discovery | Windows user-data paths and schema migration |
| Runtime requirements largely external to package metadata | Explicit Windows dependencies, pinned build environment, packaged assets and DLLs |

Reuse history, configuration semantics, voice metadata, queue logic and applicable
tests. Keep Linux imports out of Windows entry points. Preserve the visual design
in `STYLE_GUIDE.md`; GTK CSS will need translation into Qt styling.

## Separate voice pickers and backward compatibility

The Windows UI must provide a dedicated **Microsoft voices** dropdown, separate
from the existing Piper voice choices. Keep the current Piper names, custom model
discovery and saved model selection intact. Do not merge installed Microsoft voices
into the Piper list or replace Piper model paths with Windows voice IDs.

Add an explicit speech-provider choice (Piper / Microsoft) to make the active
engine clear. Each provider remembers its own selection: retain `model_path` for
Piper and add `microsoft_voice_id` for Windows voices. Add `speech_provider` with
Piper as the default for existing configurations. Switching providers must not
overwrite either saved voice. Settings and overlay must agree on the active provider;
messages and samples use that provider through the same routing rules.

Only list Microsoft voices actually exposed by the supported Windows API. If the
saved voice becomes unavailable, preserve its ID and require an explicit selection;
do not silently choose another voice. On unsupported platforms, leave Piper usable
and make Microsoft availability clear. Optional Windows discovery failures must
not prevent Piper startup, selection or playback.

Before merging the Windows implementation, test upgrades from existing config
files, provider switching in both directions, missing Microsoft voices, and Piper
messages/samples with a saved Microsoft preference. Assert that existing model
paths and unrelated settings survive load/save. This is part of the Windows release
scope. The later explicit authorization for the preliminary preference picker
supersedes the earlier cancellation of that separate dropdown work.

## Framework choices and alternatives

| Area | Recommendation | Reason and alternative |
| --- | --- | --- |
| UI | PySide6, Qt Widgets | Reuses Python and supports the compact custom UI. Qt documents desktop packaging. Packaged GTK remains possible, but requires bundling its Windows runtime and replacing Linux integration anyway. |
| Microsoft speech | PyWinRT projections for `Windows.Media.SpeechSynthesis` and stream handling | Calls Windows synthesis APIs from Python. Probe SAPI through COM only if the desired voice is absent from WinRT. |
| Piper | Start by testing the existing `piper-tts==1.4.2` pin | PyPI supplies a Windows x64 wheel. Newer releases exist; evaluate upgrades separately after the baseline works. |
| Audio | `sounddevice`, PortAudio, WASAPI shared mode | Explicit output streams and format conversion. Validate stable endpoint identity and reconnect behavior before committing to this backend. |
| Windows integration | Win32 calls through `ctypes`; Qt native event handling | `RegisterHotKey`, unregister on exit, native activation. Use Qt local IPC for second-launch activation. |
| Executable | PyInstaller directory mode | Bundles Python and dependencies; easier to inspect native files and keep voice data external. Qt's recommended `pyside6-deploy` is the fallback to compare if freezing fails. |
| Installer | Inno Setup | Normal installer/uninstaller and per-user mode with `PrivilegesRequired=lowest`. |
| Build and release | Windows CI runner, pytest, SignTool, SHA-256 manifest | Repeatable build, signatures and independently verifiable downloads. |

A C# desktop shell is an alternative if the Python Windows probes expose a
fundamental integration problem, but would add a second runtime or a substantial
core rewrite. Electron/Tauri would also add a web UI and an interprocess boundary
to the existing Python engine. Neither solves virtual microphone routing by itself;
that extra architecture is not justified for this first release.

Sources: [Qt for Python](https://doc.qt.io/qtforpython-6/),
[Qt deployment](https://doc.qt.io/qtforpython-6/deployment/index.html),
[GTK on Windows](https://www.gtk.org/docs/installations/windows),
[PyWinRT](https://github.com/pywinrt/pywinrt),
[Piper 1.4.2 Windows wheel](https://pypi.org/project/piper-tts/1.4.2/),
[WASAPI settings](https://python-sounddevice.readthedocs.io/en/latest/api/platform-specific-settings.html),
[PyInstaller](https://pyinstaller.org/en/stable/index.html),
[Inno Setup privileges](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm).

## Audio routing contract

Caspr plays to a Windows **render/output endpoint**. Discord receives audio from
an associated **capture/input endpoint**. Selecting a playback device in Python
does not create a system microphone. Preserve two supported configurations:

1. **Existing Realtek Stereo Mix:** Caspr plays to the Realtek output captured by
   Stereo Mix; Discord selects Stereo Mix. This remains the initial compatibility
   path and requires hardware testing. It can also capture other audio played to
   that output. Disable samples unless a separately verified preview output exists.
2. **Optional VB-CABLE:** Caspr plays messages to **CABLE Input**; Discord selects
   **CABLE Output**. Caspr separately plays monitoring and samples to headphones.
   Samples never use CABLE Input. Confirm that Windows Listen/other mixers are not
   routing those headphones back into the capture path.

Do not change the user's system default devices or Discord Push to Talk behavior.
Validate their existing PTT workflow; sending text alone does not guarantee that
Discord is transmitting. Do not promise physical-microphone mixing in v1.

Store message and preview destinations separately. Never silently fall back to the
system default when a selected endpoint disappears. Fail closed for previews;
require an explicit new selection after an ambiguous device change. Do not persist
PortAudio's transient numeric device index as identity. Probe a Windows endpoint-ID
mapping; if the wrapper cannot provide dependable identity, add a Core Audio adapter
before enabling private previews. Test sample-rate/channel conversion, including
Piper output against 44.1/48 kHz devices. Avoid duplicate local playback when the
message destination already is the chosen local output.

Windows device names and disconnected endpoints cannot prove an arbitrary external
mixer's routing. The privacy acceptance claim applies to the documented, verified
configurations. Disable previews when isolation cannot be established.

For v1, guide users to the official optional cable installer. The driver may require
administrator rights and a restart; Caspr itself should run as a normal user. Do
not bundle it by default. VB-Audio permits redistribution under stated conditions,
including donationware attribution and different terms for some organizational
uses; bundling requires reviewing those terms. Do not create a custom driver:
Microsoft's SysVAD sample is a driver development starting point, not a finished
redistributable Caspr microphone.

Sources: [VB-CABLE](https://vb-audio.com/Cable/),
[VB-CABLE redistribution terms](https://vb-audio.com/Services/licensing.htm),
[SysVAD sample](https://github.com/Microsoft/Windows-driver-samples/tree/main/audio/sysvad),
[driver signing](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/windows-driver-signing-tutorial).

## Speech and application behavior

Enumerate `SpeechSynthesizer.AllVoices`, record returned IDs and locales, and test
Microsoft James on the target machine. Microsoft documents that this API uses
Microsoft-signed installed voices; it does not guarantee James will be exposed.
If absent, probe SAPI separately and report the result. Do not copy APM/BEP/INI
resources, patch voice registry registrations, or bundle Microsoft voice files.
James remains a release gate for the original user's workflow until verified or
explicitly rescoped. Both providers must produce audio for the shared router rather
than speaking directly to the default device.

Run synthesis off the UI thread; use a worker event loop for WinRT async operations
and marshal UI callbacks safely. Keep the speech engine loaded where practical.
Preserve FIFO speech, configurable delay, 0.5-second silent lead-in, volume, the
25-message in-memory history, Enter-to-send/hide and Escape-to-clear/hide. Samples
say “I love text-to-speech” and respect selected voice and volume independently
of monitoring. Settings persist automatically. Production debug defaults off;
no message text in logs or persistent history. Clean up temporary speech audio.

Use a configurable default such as Ctrl+Alt+T, check registration conflicts, and
retain tray access if registration fails. Do not copy the Linux Super shortcut:
Microsoft reserves Windows-key combinations for the OS. A second process should
ask the existing process to open the overlay, then exit. Settings-close keeps the
tray process alive; explicit Quit cleans up hotkeys, streams and workers.

Sources: [installed voice enumeration](https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer.allvoices),
[SpeechSynthesizer](https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer),
[RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey).

## Packaging and deployment

- Install program files under `%LOCALAPPDATA%\Programs\Caspr TTS`.
- Store configuration under `%LOCALAPPDATA%\Caspr TTS\config.json` and writable
  models under `%LOCALAPPDATA%\Caspr TTS\data\voices`. This is the installed
  app's data/voices folder; repository development can retain its current folder.
- Add an Open voices folder action. Users drop `.onnx` and matching `.onnx.json`
  files there and restart; no model import GUI. Validate both files during discovery.
- Keep user-added models and settings through upgrades. Uninstall removes program
  files and shortcuts; preserve user data by default. Seed bundled models only when
  absent, without overwriting a user's file of the same name.
- Bundle Python, Qt plugins/assets, Piper native dependencies and phonemizer data,
  ONNX Runtime, PortAudio and required WinRT projections. Inventory runtime DLL
  requirements using the frozen build; do not assume a developer machine proves
  completeness. Users should not install Python, MSYS2 or Visual Studio.
- Prefer an installer over portable distribution for v1. No self-updater initially:
  publish versioned installers and support an in-place upgrade using a stable app ID.
- Use Windows CI for PyInstaller; it is not a cross-compiler. Pin the tested Python
  minor (start the probe with 3.11 x64), dependencies, build tools and runner image.
  Produce `Caspr-TTS-<version>-windows-x64-setup.exe`, checksums, release notes and
  dependency/license inventory. Keep the directory bundle as a diagnostic artifact.
- Sign application binaries and installer/uninstaller, timestamp signatures, and
  verify them after packaging. Use a trusted signing identity and protected release
  credentials. Signing does not constitute a promise of zero reputation prompts.
- Distribute through a versioned project release download initially. Defer Store,
  MSIX, winget and automatic updates until the installer and audio setup are proven.

Piper's current engine is GPL-3.0-or-later; this is a distribution decision, not
just a technical dependency. Decide Caspr's compatible licensing/source-delivery
approach before shipping it. Qt/PySide also carries open-source or commercial
license obligations. Audit each bundled voice model's own model card/license and
include provenance and attribution; engine licensing does not establish model
redistribution rights. Do not assume subprocess packaging removes obligations.

Sources: [Piper package and license](https://pypi.org/project/piper-tts/1.4.2/),
[Qt licensing](https://doc.qt.io/qtforpython-6/),
[PyInstaller bundle behavior](https://www.pyinstaller.org/en/stable/operating-mode.html),
[Inno signed uninstaller](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm),
[Microsoft signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).

## Implementation stages and exit gates

| Stage | Deliverable | Exit gate |
| --- | --- | --- |
| 1. Windows feasibility | Voice enumeration/synthesis probe, endpoint/playback probe, tiny frozen build | James tested on target PC; Piper works without installed Python; Realtek and optional cable paths understood; private preview behavior measured |
| 2. Portable core | Provider/router interfaces, separate saved voice selections, additive config migration and data paths | Existing Piper configs retain their model and default provider; tests cover provider switching, queue recovery and sample isolation |
| 3. Windows backend | WinRT + Piper engines, endpoint selection and independent streams | Correct formats, ordering, volume, no preview fallback on unplug; sleep/resume and default-device changes tested |
| 4. Windows shell | Qt overlay/settings/tray, dedicated Microsoft dropdown, preserved Piper choices, provider selector, hotkey and single-instance activation | Independent voice selections persist; interaction parity; no overlap or UI blocking; DPI/multiple-monitor and foreground-app checks pass |
| 5. Installer | Frozen app, Inno script, Windows CI, licenses and signatures | Install/run offline without dev tools; upgrade preserves settings/models; uninstall cleanly removes app |
| 6. Release candidate | Tested signed installer, checksums, release notes and setup guide | Clean Windows 10/11 tests and target hardware/Discord acceptance pass before publishing prerelease |

Do not spend the UI implementation budget before stage 1 resolves James and the
recording route. A Windows CI runner can validate compilation and basic synthesis;
it cannot substitute for the original Realtek hardware and a real Discord call.

Manual acceptance must include: first install and missing optional cable, James
present/absent, Piper pair added after install, monitoring on/off, 0/100% volume,
rapid submissions and synthesis failure, endpoint unplug/replug, duplicate device
names, sleep/resume, default output changes, hotkey conflicts, second launch,
100/150/200% scaling, spaces/non-ASCII in paths, upgrade and uninstall. Record the
Discord input to verify previews never arrive in supported configurations; with
Stereo Mix and no isolated preview endpoint, verify previews are disabled.

## Remaining decisions

- Exact target Windows build and whether James is exposed by WinRT or SAPI.
- Verified Realtek preview endpoint, or previews disabled for that configuration.
- Caspr distribution license, final bundled Piper models and attribution.
- Signing identity/provider and release hosting credentials.
- Dependency versions and final audio adapter after the Windows probes.

No Windows runtime, hardware or installer tests were performed for this planning
change. Estimates should follow the feasibility stage, whose results determine
whether native integration needs more work.
