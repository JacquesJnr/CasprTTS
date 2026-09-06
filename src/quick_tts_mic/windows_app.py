"""Caspr TTS Windows entry point. Does not import GTK, Gio or PipeWire."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def runtime_smoke():
    from .windows_probe import smoke
    result = smoke()
    import numpy as np
    from scipy.signal import resample_poly
    import soundcard
    import piper
    from piper.phonemize_espeak import EspeakPhonemizer
    # Exercise native phonemizer and its packaged data without downloading a model.
    phonemizer = EspeakPhonemizer()
    if not phonemizer.phonemize("en-us", "test"):
        raise RuntimeError("Piper phonemizer returned no phonemes")
    if not (Path(soundcard.__file__).parent / "mediafoundation.py.h").is_file():
        raise RuntimeError("SoundCard native definitions missing")
    resample_poly(np.zeros((16, 2), dtype=np.float32), 2, 1)
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
    report = {"ok": False}
    try:
        if sys.platform != "win32":
            raise RuntimeError("This entry point requires Windows; use quick-tts-mic on Linux.")
        if args.smoke_test:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        from PySide6.QtCore import QLockFile
        from .windows_runtime import WindowsConfig, data_dir
        from .windows_ui import Controller, STYLE, icon
        app = QApplication([sys.argv[0]])
        app.setApplicationName("Caspr TTS")
        app.setOrganizationName("Caspr TTS")
        app.setQuitOnLastWindowClosed(False)
        app.setStyleSheet(STYLE)
        app.setWindowIcon(icon())
        if args.smoke_test:
            report.update(runtime_smoke())
            controller = Controller(app, WindowsConfig(), start_services=False)
            controller.settings.show()
            controller.overlay.show()
            app.processEvents()
            if controller.settings.grab().isNull() or controller.overlay.grab().isNull():
                raise RuntimeError("Qt window rendering failed")
            controller.close()
            report.update(ok=True, qt="settings and overlay rendered", hardware="not tested")
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
        if not args.smoke_test and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "Caspr TTS could not start", 0x10)
        return 1
    finally:
        if args.smoke_report:
            args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
            args.smoke_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.smoke_test and sys.stdout:
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
