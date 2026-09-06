# Build only on Windows with the pinned Python 3.11 x64 environment.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parents[1]
datas = collect_data_files("quick_tts_mic")
binaries = []
hiddenimports = ["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtNetwork"]
# These packages load extension modules, DLLs, headers or phonemizer resources
# dynamically. Qt's own hooks select the platform plugins for imported modules.
for package in ("piper", "onnxruntime", "soundcard", "_sounddevice_data", "winrt"):
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
):
    datas += copy_metadata(distribution)
# SoundCard reads this header at runtime using __file__.
datas += collect_data_files("soundcard", includes=["*.h"])
a = Analysis(
    [str(root / "packaging/windows/launcher.py")],
    pathex=[str(root / "src")], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=["gi", "tkinter", "PyQt5", "PyQt6"],
    noarchive=False,
)
# The upstream sounddevice hook also gathers ASIO; filter the final TOC.
a.binaries = [item for item in a.binaries if not item[0].lower().endswith("-asio.dll")]
a.datas = [item for item in a.datas if not item[0].lower().endswith("-asio.dll")]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CasprTTS",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CasprTTS")
