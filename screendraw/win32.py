"""Thin ctypes wrappers around the Win32 APIs the overlay needs."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# --- window styles -----------------------------------------------------
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

# --- SetWindowPos ------------------------------------------------------
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

# --- ShowWindow --------------------------------------------------------
SW_SHOWNA = 8  # show in its current state without stealing focus

# --- system metrics ----------------------------------------------------
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

GA_ROOT = 2

user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]


def enable_dpi_awareness() -> None:
    """Opt into per-monitor DPI awareness so pixel geometry is exact.

    Without this Windows silently scales coordinates on high-DPI displays and
    the overlay ends up misaligned with what the user actually sees.
    """
    try:
        # PER_MONITOR_AWARE_V2 (Windows 10 1703+)
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def virtual_screen() -> tuple[int, int, int, int]:
    """Return (x, y, width, height) of the bounding box covering all monitors."""
    return (
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def hwnd_of(widget) -> int:
    """Return the top-level window handle backing a Tk widget."""
    return user32.GetAncestor(widget.winfo_id(), GA_ROOT)


def _update_ex_style(hwnd: int, add: int = 0, remove: int = 0) -> None:
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | add) & ~remove)


def set_click_through(widget, enabled: bool) -> None:
    """Make a window ignore the mouse entirely (WS_EX_TRANSPARENT)."""
    hwnd = hwnd_of(widget)
    if enabled:
        _update_ex_style(hwnd, add=WS_EX_TRANSPARENT | WS_EX_LAYERED)
    else:
        _update_ex_style(hwnd, remove=WS_EX_TRANSPARENT)


def hide_from_taskbar(widget) -> None:
    """Keep a window out of the taskbar and the Alt+Tab switcher."""
    _update_ex_style(hwnd_of(widget), add=WS_EX_TOOLWINDOW)


def raise_topmost(widget) -> None:
    """Move a window to the top of the always-on-top band without focusing it."""
    user32.SetWindowPos(
        hwnd_of(widget), wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


def ensure_visible(widget) -> None:
    """Force a window Tk believes is mapped to actually be shown.

    A process launched with ``STARTF_USESHOWWINDOW`` and ``SW_HIDE`` (which is
    how background launchers and shortcuts that suppress the console start us)
    has that flag applied to its *first* top-level window. Tk still thinks the
    window is mapped, so it never corrects this itself.
    """
    user32.ShowWindow(hwnd_of(widget), SW_SHOWNA)
