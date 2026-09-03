"""System-wide hotkeys.

``RegisterHotKey`` delivers ``WM_HOTKEY`` to the message queue of the thread
that registered it, so the hotkeys live on their own thread with a private
message loop. Triggered actions are handed back to the Tk thread through a
queue, because Tk is not thread-safe.
"""

from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

user32.RegisterHotKey.argtypes = [
    wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL


class HotkeyManager:
    """Registers global hotkeys and queues their action names."""

    def __init__(self) -> None:
        self._bindings: dict[int, str] = {}
        self._specs: list[tuple[int, int, int]] = []
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self.failed: list[str] = []

    def bind(self, action: str, modifiers: int, virtual_key: int) -> None:
        """Register ``action`` under a modifier + key combination."""
        hotkey_id = len(self._specs) + 1
        self._bindings[hotkey_id] = action
        self._specs.append((hotkey_id, modifiers | MOD_NOREPEAT, virtual_key))

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="screendraw-hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        registered: list[int] = []
        for hotkey_id, mods, vk in self._specs:
            if user32.RegisterHotKey(None, hotkey_id, mods, vk):
                registered.append(hotkey_id)
            else:
                self.failed.append(self._bindings[hotkey_id])
        self._ready.set()

        msg = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):  # WM_QUIT or error
                break
            if msg.message == WM_HOTKEY:
                action = self._bindings.get(int(msg.wParam))
                if action:
                    self._queue.put(action)

        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)

    def poll(self) -> list[str]:
        """Drain and return the actions triggered since the last call."""
        actions = []
        while True:
            try:
                actions.append(self._queue.get_nowait())
            except queue.Empty:
                return actions

    def stop(self) -> None:
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
