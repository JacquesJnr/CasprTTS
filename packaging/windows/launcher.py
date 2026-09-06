"""PyInstaller entry point; keep runtime implementation in windows_app."""
from quick_tts_mic.windows_app import main

if __name__ == "__main__":
    raise SystemExit(main())
