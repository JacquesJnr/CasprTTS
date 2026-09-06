"""Caspr TTS Windows entry point. Does not import GTK, Gio or PipeWire."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Callable


class _SmokeReporter:
    """Flush a checkpoint so a windowed process cannot hide its last stage."""

    def __init__(self, path: Path | None):
        self.path = path
        self.report = {"ok": False, "stage": "entry"}

    def checkpoint(self, stage: str, **values):
        self.report.update(stage=stage, **values)
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as output:
            json.dump(self.report, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())

    def finish(self, **values):
        self.report.update(values)
        self.checkpoint(self.report.get("stage", "finished"))


def runtime_smoke(checkpoint: Callable[..., None] = lambda *_args, **_kwargs: None):
    checkpoint("native_imports_begin")
    import sounddevice as sd
    checkpoint("sounddevice_imported")
    import onnxruntime
    checkpoint("onnxruntime_imported")
    import piper
    checkpoint("piper_imported")
    checkpoint("winrt_foundation_begin")
    import winrt.windows.foundation
    checkpoint("winrt_foundation_collections_begin")
    import winrt.windows.foundation.collections
    checkpoint("winrt_speech_begin")
    import winrt.windows.media.speechsynthesis
    checkpoint("winrt_streams_begin")
    import winrt.windows.storage.streams
    checkpoint("winrt_enumeration_begin")
    import winrt.windows.devices.enumeration
    checkpoint("winrt_media_devices_begin")
    import winrt.windows.media.devices
    checkpoint("winrt_imported")
    result = dict(portaudio=sd.get_portaudio_version(), onnxruntime=onnxruntime.__version__,
                  imports="ok", frozen=bool(getattr(sys, "frozen", False)),
                  python=sys.version.split()[0], windows=sys.platform)
    checkpoint("native_calls_begin")
    import numpy as np
    from scipy.signal import resample_poly
    import soundcard
    from piper.phonemize_espeak import EspeakPhonemizer
    checkpoint("phonemizer_begin")
    # Exercise native phonemizer and its packaged data without downloading a model.
    phonemizer = EspeakPhonemizer()
    if not phonemizer.phonemize("en-us", "test"):
        raise RuntimeError("Piper phonemizer returned no phonemes")
    if not (Path(soundcard.__file__).parent / "mediafoundation.py.h").is_file():
        raise RuntimeError("SoundCard native definitions missing")
    checkpoint("phonemizer_complete")
    resample_poly(np.zeros((16, 2), dtype=np.float32), 2, 1)
    checkpoint("resampler_complete")
    result.update(soundcard="imported", scipy="resampler exercised", piper="phonemizer exercised")
    return result


def main(argv=None):
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] == "--probe":
        from .windows_probe import main as probe_main
        return probe_main(args_list[1:])
    parser = argparse.ArgumentParser(description="Caspr TTS for Windows")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-report", type=Path)
    args = parser.parse_args(args_list)
    reporter = _SmokeReporter(args.smoke_report)
    report = reporter.report
    try:
        reporter.checkpoint("app_entry", argv=args_list)
        if sys.platform != "win32":
            raise RuntimeError("This entry point requires Windows; use quick-tts-mic on Linux.")
        if args.smoke_test:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        reporter.checkpoint("qt_imports_begin")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        from PySide6.QtCore import QLockFile
        from .windows_runtime import WindowsConfig, data_dir
        from .windows_ui import Controller, STYLE, icon
        reporter.checkpoint("qt_imports_complete")
        app = QApplication([sys.argv[0]])
        app.setApplicationName("Caspr TTS")
        app.setOrganizationName("Caspr TTS")
        app.setQuitOnLastWindowClosed(False)
        app.setStyleSheet(STYLE)
        app.setWindowIcon(icon())
        if args.smoke_test:
            reporter.checkpoint("qt_app_created")
            report.update(runtime_smoke(reporter.checkpoint))
            reporter.checkpoint("qt_windows_begin")
            controller = Controller(app, WindowsConfig(), start_services=False)
            controller.settings.show()
            controller.overlay.show()
            app.processEvents()
            if controller.settings.grab().isNull() or controller.overlay.grab().isNull():
                raise RuntimeError("Qt window rendering failed")
            controller.close()
            reporter.checkpoint("qt_windows_complete")
            report.update(ok=True, qt="settings and overlay rendered", hardware="not tested")
            reporter.finish(stage="complete")
            return 0
        root = data_dir()
        root.mkdir(parents=True, exist_ok=True)
        server_name = "CasprTTS-" + hashlib.sha256(str(root).encode()).hexdigest()[:20]
        lock = QLockFile(str(root / "instance.lock"))
        if not lock.tryLock(0):
            client = QLocalSocket()
            client.connectToServer(server_name)
            if not client.waitForConnected(3000):
                raise RuntimeError("Caspr TTS is already starting or running but could not be activated.")
            client.write(b"show\n")
            client.waitForBytesWritten(1000)
            client.disconnectFromServer()
            return 0
        QLocalServer.removeServer(server_name)
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(server_name):
            raise RuntimeError("Could not start single-instance activation server.")
        controller = Controller(app)
        def activate():
            while server.hasPendingConnections():
                connection = server.nextPendingConnection()
                controller.overlay.open()
                connection.disconnectFromServer()
                connection.deleteLater()
        server.newConnection.connect(activate)
        controller.show_settings()
        code = app.exec()
        server.close()
        lock.unlock()
        return code
    except Exception as error:
        report.update(ok=False, error=type(error).__name__, detail=str(error))
        reporter.checkpoint("error")
        if not args.smoke_test and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "Caspr TTS could not start", 0x10)
        return 1
    finally:
        if args.smoke_report:
            reporter.checkpoint(report.get("stage", "finished"))
        if args.smoke_test and sys.stdout:
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
