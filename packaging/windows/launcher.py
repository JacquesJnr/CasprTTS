"""PyInstaller entry point; keep runtime implementation in windows_app."""
import faulthandler
import json
from pathlib import Path
import sys


def _early_smoke_checkpoint(argv):
    if "--smoke-test" not in argv or "--smoke-report" not in argv:
        return None
    try:
        report = Path(argv[argv.index("--smoke-report") + 1])
    except IndexError:
        return None
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"ok": False, "stage": "launcher_start"}, indent=2) + "\n", encoding="utf-8")
    trace = report.with_name(report.name + ".traceback.log").open("a", encoding="utf-8")
    faulthandler.dump_traceback_later(90, file=trace, repeat=False)
    return trace


_smoke_trace = _early_smoke_checkpoint(sys.argv[1:])

from quick_tts_mic.windows_app import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        if _smoke_trace is not None:
            faulthandler.cancel_dump_traceback_later()
            _smoke_trace.close()
