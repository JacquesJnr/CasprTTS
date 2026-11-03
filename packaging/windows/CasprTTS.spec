# Build only on Windows with the pinned Python 3.11 x64 environment.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parents[1]
datas = collect_data_files("quick_tts_mic")
binaries = []
# pywebview picks its Windows backend (WinForms + WebView2 through pythonnet) and pystray
# its tray backend at runtime, so name them explicitly.
hiddenimports = ["webview.platforms.winforms", "webview.platforms.edgechromium", "clr", "pystray._win32"]
# These packages load extension modules, DLLs, headers or phonemizer resources dynamically.
for package in ("piper", "onnxruntime", "soundcard", "_sounddevice_data", "winrt",
                "webview", "pythonnet", "clr_loader"):
    data, native, imports = collect_all(package)
    # Diagnostic PortAudio uses WASAPI; do not redistribute the optional ASIO binary.
    datas += [item for item in data if not item[0].lower().endswith("-asio.dll")]
    binaries += [item for item in native if not item[0].lower().endswith("-asio.dll")]
    hiddenimports += imports
for distribution in (
    "piper-tts", "onnxruntime", "soundcard", "sounddevice", "winrt-runtime",
    "winrt-Windows.Media.SpeechSynthesis", "winrt-Windows.Storage.Streams",
    "winrt-Windows.Foundation", "winrt-Windows.Foundation.Collections",
    "winrt-Windows.Devices.Enumeration", "winrt-Windows.Media.Devices",
    "pywebview", "pythonnet", "clr_loader", "pystray", "pillow",
):
    datas += copy_metadata(distribution)
# SoundCard reads this header at runtime using __file__.
datas += collect_data_files("soundcard", includes=["*.h"])
# The React UI, built by `npm --prefix web run build`; web_app loads it from sys._MEIPASS/web/dist.
dist = root / "web" / "dist"
if not (dist / "index.html").is_file():
    raise SystemExit("Build the UI first: npm --prefix web ci && npm --prefix web run build")
datas += [(str(dist), "web/dist")]
# x64 only: drop pywebview/clr_loader binaries for other architectures and Android.
SKIP = ("win-arm64", "win-x86", "x86.dll", "pywebview-android.jar", "dlls/x86", ".pdb")
a = Analysis(
    [str(root / "packaging/windows/launcher.py")],
    pathex=[str(root / "src")], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[],
    # Build/test-only modules reached via pytest, onnxruntime.transformers and cffi's build shim.
    # Bundling pkg_resources adds a startup hook that crashes on setuptools 80 (missing backports).
    excludes=["gi", "tkinter", "PyQt5", "PyQt6", "PySide6",
              "pkg_resources", "setuptools", "pytest", "_pytest", "onnxruntime.transformers"],
    noarchive=False,
)
# The upstream sounddevice hook also gathers ASIO; filter the final TOC.
a.binaries = [item for item in a.binaries if not item[0].lower().endswith("-asio.dll")
              and not any(s in item[0].replace("\\", "/").lower() for s in SKIP)]
a.datas = [item for item in a.datas if not item[0].lower().endswith("-asio.dll")
           and not any(s in item[0].replace("\\", "/").lower() for s in SKIP)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CasprTTS",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CasprTTS")
