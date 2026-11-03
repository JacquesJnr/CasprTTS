"""PyInstaller entry point: the pywebview app, the hardware probe, or a frozen-bundle smoke test."""
import faulthandler
import json
import os
from pathlib import Path
import sys


def _report_writer(argv):
    """Smoke runs write a checkpoint after every stage so a windowed process can't hide where it died."""
    if "--smoke-report" not in argv:
        return lambda **_: None, None
    report_path = Path(argv[argv.index("--smoke-report") + 1])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"ok": False, "stage": "launcher_start"}
    trace = report_path.with_name(report_path.name + ".traceback.log").open("a", encoding="utf-8")
    faulthandler.dump_traceback_later(90, file=trace, repeat=False)

    def checkpoint(**values):
        report.update(values)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    checkpoint()
    return checkpoint, trace


def _log_to_file():
    """The windowed exe has no console: send pywebview logs and stderr to a file users can share."""
    import logging
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Caspr TTS"
    root.mkdir(parents=True, exist_ok=True)
    stream = (root / "caspr.log").open("w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    logging.basicConfig(stream=stream, level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
    logging.getLogger("pywebview").setLevel(logging.DEBUG)


def render_ui(webview, index, timeout=45):
    """Open the app's real windows (overlay first, as the app does) with its exact options.

    Passes only when each page's JS reaches the Python bridge.
    """
    import threading
    from quick_tts_mic.web_app import window_options

    class Bridge:
        def __init__(self, kind):
            self.kind_name, self.called = kind, threading.Event()

        def kind(self):
            return self.kind_name

        def state(self):
            self.called.set()  # the page's module script ran and reached the Python bridge
            raise RuntimeError("smoke test: no app state")

    bridges = [Bridge("overlay"), Bridge("settings")]
    windows = [webview.create_window(url=str(index), js_api=b, **window_options(b.kind_name)) for b in bridges]

    def finish():
        for b in bridges:
            b.called.wait(timeout)
        for window in windows:
            window.destroy()

    threading.Thread(target=finish, daemon=True).start()
    webview.start(http_server=True)
    missing = [b.kind_name for b in bridges if not b.called.is_set()]
    if missing:
        raise RuntimeError(f"UI did not load in WebView2 for: {', '.join(missing)}")


def smoke(checkpoint):
    """Load every native piece and render the UI once in WebView2; no audio, hardware or network."""
    checkpoint(stage="imports_begin")
    import numpy as np
    import onnxruntime
    import piper
    import sounddevice as sd
    import soundcard
    from scipy.signal import resample_poly
    checkpoint(stage="audio_and_piper_imported")
    import winrt.windows.foundation.collections  # noqa: F401
    import winrt.windows.media.speechsynthesis  # noqa: F401
    import winrt.windows.storage.streams  # noqa: F401
    import winrt.windows.devices.enumeration  # noqa: F401
    import winrt.windows.media.devices  # noqa: F401
    checkpoint(stage="winrt_imported")
    import webview
    from webview.platforms import winforms  # noqa: F401  (pythonnet + .NET Framework + WebView2 SDK)
    import pystray._win32  # noqa: F401
    from quick_tts_mic.web_app import DIST_INDEX
    from quick_tts_mic.windows_shell import tray_image
    checkpoint(stage="ui_imported")
    from piper.phonemize_espeak import EspeakPhonemizer
    if not EspeakPhonemizer().phonemize("en-us", "test"):
        raise RuntimeError("Piper phonemizer returned no phonemes")
    if not (Path(soundcard.__file__).parent / "mediafoundation.py.h").is_file():
        raise RuntimeError("SoundCard native definitions missing")
    if not DIST_INDEX.is_file():
        raise RuntimeError(f"Bundled UI missing: {DIST_INDEX}")
    resample_poly(np.zeros((16, 2), dtype=np.float32), 2, 1)
    tray_image()
    checkpoint(stage="render_begin")
    render_ui(webview, DIST_INDEX)
    checkpoint(stage="render_complete")
    checkpoint(stage="complete", ok=True, portaudio=sd.get_portaudio_version(),
               onnxruntime=onnxruntime.__version__, piper=getattr(piper, "__version__", "imported"),
               pywebview=getattr(webview, "__version__", "imported"),
               frozen=bool(getattr(sys, "frozen", False)), python=sys.version.split()[0],
               hardware="not tested")
    return 0


def main(argv):
    if argv[:1] == ["--probe"]:
        from quick_tts_mic.windows_probe import main as probe_main
        return probe_main(argv[1:])
    checkpoint, trace = _report_writer(argv)
    try:
        if "--smoke-test" in argv:
            return smoke(checkpoint)
        _log_to_file()
        from quick_tts_mic.web_app import main as app_main
        return app_main()
    except Exception as error:
        checkpoint(stage="error", error=type(error).__name__, detail=str(error))
        if "--smoke-test" not in argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "Caspr TTS could not start", 0x10)
        return 1
    finally:
        if trace is not None:
            faulthandler.cancel_dump_traceback_later()
            trace.close()


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if "--smoke-test" in sys.argv:
        # pywebview leaves non-daemon threads behind after webview.start() returns; the report is
        # already written, so exit now instead of hanging until smoke.ps1's timeout.
        os._exit(code)
    raise SystemExit(code)
