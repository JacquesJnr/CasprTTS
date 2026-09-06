# Windows build and release

Caspr TTS targets Python 3.11 x64 and a directory-mode PyInstaller bundle inside a
per-user Inno Setup installer. End users do not need Python, Visual Studio or
MSYS2. Windows 10 22H2 x64 and Windows 11 x64 are the intended manual test targets;
the Windows Server 2022 CI runner is not a substitute for those tests.

## Download and install

After a maintainer explicitly publishes a Windows release, download
`Caspr-TTS-<version>-windows-x64-setup.exe` and `SHA256SUMS.txt` from
[GitHub Releases](https://github.com/JacquesJnr/CasprTTS/releases). Compare the
installer's `Get-FileHash -Algorithm SHA256` result with its manifest entry.
The default CI installer is unsigned; signing requires the maintainer's certificate.

Program files install to `%LOCALAPPDATA%\Programs\Caspr TTS`. Configuration lives
at `%LOCALAPPDATA%\Caspr TTS\config.json`; user models live at
`%LOCALAPPDATA%\Caspr TTS\data\voices`. Run a newer installer as the same Windows
user to upgrade. The stable installer AppId must never change. Upgrade and
uninstall preserve the separate user-data directory. Quit Caspr before upgrading.
Uninstall through Windows Settings or the Start menu entry.

No voice models, Microsoft voice files or audio drivers are bundled. Add a Piper
`.onnx` file and matching `.onnx.json` to the voices folder, then restart. Installed
Microsoft voices are discovered from Windows. James availability must be tested
on the intended PC. For Stereo Mix, select its associated Realtek output for
messages; for optional VB-CABLE select CABLE Input in Caspr and CABLE Output in
Discord. Install optional drivers from their publisher. The app does not change
system defaults or automate Discord Push to Talk. Confirm preview isolation on the
actual audio route before using samples.

## Reproduce a build

Use a clean Windows x64 checkout and PowerShell 7. Install Python **3.11.9 x64**
and [Inno Setup **6.4.3**](https://github.com/jrsoftware/issrc/releases/tag/is-6_4_3).
The CI workflow verifies the Inno installer SHA-256 before running it. The runner
is pinned to `windows-2022` (GitHub updates the image contents).

```powershell
py -3.11 -m venv .venv-windows
.\.venv-windows\Scripts\Activate.ps1
python -m pip install --require-hashes --only-binary=:all: -r requirements-windows-build.txt
python -m pip install --no-deps --no-build-isolation .
python -m pip check
python -m pytest -q
./packaging/windows/build.ps1 -Version 0.1.0
```

Build from a committed clean checkout: the source archive uses `git archive HEAD`.
The runtime lock contains every dependency, including Windows-only transitive
requirements. The build lock includes it and pins PyInstaller, hooks, pip,
setuptools and pytest. Each requirement has the SHA-256 of its Windows x64 or
universal wheel. These locks intentionally cannot install on Linux or ARM64.
Windows wheel resolution and hashes were verified on 2026-09-06; native execution
compatibility must pass Windows CI before calling the pins tested.

Baseline versions: Piper 1.4.2, PySide6 6.8.3, ONNX Runtime 1.22.1, NumPy 2.2.6,
SciPy 1.15.3, SoundCard 0.4.6, sounddevice 0.5.2 and PyWinRT 3.2.1. SoundCard handles
WASAPI endpoint-ID playback; sounddevice/PortAudio is diagnostic. WinRT runtime and
six projections are collected: Foundation, Foundation.Collections,
Media.SpeechSynthesis, Storage.Streams, Devices.Enumeration and Media.Devices.
PyInstaller collects native libraries, Piper espeak data, SoundCard's
`mediafoundation.py.h`, PortAudio and Qt platform plugins. No Linux GTK entry point
is imported by the launcher.

To update pins, resolve with `pip download --only-binary=:all: --platform win_amd64
--python-version 3.11 --implementation cp --abi cp311`, inspect wheel metadata,
include Windows-only marker dependencies, regenerate hashes, and repeat the Windows
build and clean-machine tests. Do not loosen pins to make a release build succeed.

## Validation and outputs

The executable entry point is `quick_tts_mic.windows_app:main`:

- `CasprTTS.exe` starts the tray/settings application.
- `CasprTTS.exe --smoke-test --smoke-report <absolute-path>` constructs offscreen Qt
  windows and loads native dependencies without hardware, models or network. It
  must exit zero and write a JSON object with `"ok": true`.
- `CasprTTS.exe --probe ...` forwards to the runtime diagnostic CLI.

`smoke.ps1` waits explicitly for the windowed process, imposes a two-minute timeout,
and clears developer Python/Qt paths and reduces PATH to Windows system folders.
It runs the bundle from a different working directory. The build checks native
resource paths before smoke validation. Failures retain JSON and PyInstaller logs
as diagnostic Actions artifacts.

On a disposable Windows user account only:

```powershell
./packaging/windows/verify-installer.ps1 -Installer ./dist/release/Caspr-TTS-0.1.0-windows-x64-setup.exe
```

This refuses existing Caspr installations/data. It compiles a lower-version
installer from the same bundle, checks per-user installation, runs frozen smoke,
creates configuration/model sentinels, upgrades to the candidate, runs smoke again,
uninstalls, and verifies byte-for-byte data preservation. It leaves the sentinel
user data for inspection. It does not test migration from a historical runtime.

`dist/release/` contains the installer, a directory ZIP, a dependency/license ZIP,
`dependencies.json`, a source ZIP and `SHA256SUMS.txt`. The inventory includes all
installed build-environment packages (explicitly labelled), shipped license/notice
files, frozen native file hashes and their imported DLL names. Some build tools in
the inventory are not frozen. The source ZIP is the application checkout, not the
complete corresponding source for third-party GPL components.

Manual release acceptance still includes an offline clean Windows 10/11 machine
without developer tools, actual Piper synthesis with an approved model, Microsoft
synthesis/James, device unplug/replug, Realtek/VB-CABLE/Discord preview isolation,
hotkeys, tray/single-instance behavior, non-ASCII paths, DPI and sleep/resume. Native
smoke alone does not prove speech synthesis or physical routing works.

## CI and publishing

`.github/workflows/windows-release.yml` builds on every branch push, pull request
and optional manual dispatch. Those events only upload Actions artifacts and use
read-only repository permissions. The **orchestrator** can push this feature branch
to run CI before merging; packaging work itself does not push, tag or publish.

Only pushing an explicit `windows-v<version>` tag enables the separate `publish`
job after successful build and installer validation. It uses the `windows-release`
environment and a job-scoped contents-write token, checks the SHA-256 manifest,
and creates a GitHub **prerelease** with all assets. Configure required reviewers
on that environment and tag restrictions before enabling public releases. A
manual dispatch, including one at a tag, does not publish. Re-running a job for an
existing release fails instead of silently replacing published assets.

Release maintainers must settle Caspr licensing and corresponding-source delivery
for [Piper's GPL-3.0-or-later engine](https://pypi.org/project/piper-tts/1.4.2/),
review [Qt/PySide licensing](https://doc.qt.io/qtforpython-6/licenses.html), and
review bundled native notices before distribution. The generated inventory records
available evidence; it does not resolve those decisions. Upstream PySide6, PyWinRT
and PortAudio license texts and their source URLs/hashes are included in
`packaging/windows/licenses`; the inventory adds the installed Python license.
The optional ASIO PortAudio DLL is excluded. No model redistribution
rights are assumed.

## Optional signing

The default CI path deliberately produces an identified unsigned candidate because
no signing identity has been configured. On a protected Windows signing machine,
import an authorized code-signing certificate into the current user's certificate
store and install the Windows SDK signing tools:

```powershell
./packaging/windows/build.ps1 -Version 0.1.0 -CertificateThumbprint YOUR_CERTIFICATE_THUMBPRINT
```

This SHA-256-signs and timestamps the application, uses Inno's signing hook for the
installer and uninstaller, verifies the application and installer signatures, then
creates archives/checksums. Third-party DLL signatures are preserved. The certificate
and private key are never committed. Hardware-backed/cloud signing can supply a
separate protected build adaptation; do not claim the default CI artifacts are
signed. The tag job currently publishes the unsigned CI build and says so in notes;
a signed release requires switching it to the reviewed signing pipeline first.

References: [PyInstaller hooks](https://pyinstaller.org/en/stable/hooks.html),
[Inno per-user privileges](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm),
[Inno signed uninstaller](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm).
