"""Windows desktop integration for the pywebview shell: global hotkey and tray icon."""
from __future__ import annotations

import threading
from typing import Callable

from .windows_probe import ProbeError
from .windows_runtime import parse_hotkey

WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
WM_APP = 0x8000
HOTKEY_ID = 1


class WindowsHotkey:
    """RegisterHotKey must be called on the thread that pumps its messages, so it owns one."""

    def __init__(self, hotkey: str, on_press: Callable[[], None], on_error: Callable[[str], None]) -> None:
        import ctypes
        self._user32 = ctypes.windll.user32
        self._hotkey = hotkey
        self._on_press = on_press
        self._on_error = on_error
        self._thread_id = 0
        self._ready = threading.Event()
        threading.Thread(target=self._loop, daemon=True, name="Caspr hotkey").start()
        self._ready.wait(2)

    def change(self, hotkey: str) -> None:
        self._hotkey = hotkey
        self._user32.PostThreadMessageW(self._thread_id, WM_APP, 0, 0)

    def stop(self) -> None:
        self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def _register(self) -> None:
        self._user32.UnregisterHotKey(None, HOTKEY_ID)
        try:
            modifiers, key = parse_hotkey(self._hotkey)
        except ProbeError as error:
            return self._on_error(str(error))
        if not self._user32.RegisterHotKey(None, HOTKEY_ID, modifiers, key):
            self._on_error(f"{self._hotkey} is already used by another app. Choose another shortcut in Settings.")

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        message = wintypes.MSG()
        self._user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)  # creates this thread's queue
        self._ready.set()
        self._register()
        while self._user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                self._on_press()
            elif message.message == WM_APP:
                self._register()
        self._user32.UnregisterHotKey(None, HOTKEY_ID)


def tray_image():
    """Lime speech bubble with three bars, drawn so no icon file needs bundling."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    lime, ink = (228, 242, 34, 255), (8, 9, 10, 255)
    draw.rounded_rectangle((6, 8, 58, 48), radius=10, fill=lime)
    draw.polygon([(14, 46), (14, 58), (26, 46)], fill=lime)
    for x, half in ((20, 6), (32, 12), (44, 6)):
        draw.rounded_rectangle((x - 3, 28 - half, x + 3, 28 + half), radius=3, fill=ink)
    return image


def start_tray(open_overlay: Callable[[], None], open_settings: Callable[[], None], quit_app: Callable[[], None]):
    import pystray
    menu = pystray.Menu(
        pystray.MenuItem("Open message box", lambda: open_overlay(), default=True),
        pystray.MenuItem("Settings", lambda: open_settings()),
        pystray.MenuItem("Quit", lambda: quit_app()),
    )
    icon = pystray.Icon("caspr-tts", tray_image(), "Caspr TTS", menu)
    icon.run_detached()
    return icon


def round_corners(window) -> None:
    """Ask Windows 11 to round a frameless pywebview window (ignored on Windows 10)."""
    import ctypes
    try:
        hwnd = window.native.Handle.ToInt32()
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
    except Exception:
        pass  # purely cosmetic
