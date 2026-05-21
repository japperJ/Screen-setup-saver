"""Window capture — enumerate visible windows and record layout metadata."""

from __future__ import annotations

import logging
import os
from typing import Any

import win32api
import win32con
import win32gui
import win32process

log = logging.getLogger(__name__)

# Window classes that are system UI — never captured
_SKIP_CLASSES = {
    "Shell_TrayWnd",          # Taskbar
    "Shell_SecondaryTrayWnd", # Secondary taskbar
    "DV2ControlHost",         # Start menu
    "MsgrIMEWindowClass",
    "SysShadow",
    "Button",                 # Desktop 'Show Desktop' button
    "Windows.UI.Core.CoreWindow",  # UWP shell chrome
    "ApplicationFrameWindow",      # UWP host frame (has no meaningful exe itself)
    "Progman",                     # Desktop
    "WorkerW",                     # Desktop wallpaper worker
}


def _is_capturable(hwnd: int) -> bool:
    """Return True if window should be included in a captured layout."""
    if not win32gui.IsWindowVisible(hwnd):
        return False
    title = win32gui.GetWindowText(hwnd)
    if not title.strip():
        return False
    # Skip tool windows (tooltips, floating toolbars, etc.)
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False
    cls = win32gui.GetClassName(hwnd)
    if cls in _SKIP_CLASSES:
        return False
    return True


def _get_exe(hwnd: int) -> str:
    """Return the executable path for the process owning hwnd, or '' on error."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        try:
            return win32process.GetModuleFileNameEx(handle, 0)
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return ""


def _get_window_state(hwnd: int) -> str:
    """Return 'maximized', 'minimized', or 'normal'."""
    placement = win32gui.GetWindowPlacement(hwnd)
    show_cmd = placement[1]
    if show_cmd == win32con.SW_SHOWMAXIMIZED:
        return "maximized"
    if show_cmd == win32con.SW_SHOWMINIMIZED:
        return "minimized"
    return "normal"


def _get_rect(hwnd: int) -> list[int]:
    """Return [left, top, width, height] using the restore rect for min/max windows."""
    placement = win32gui.GetWindowPlacement(hwnd)
    # placement[4] is the normal (restore) rect as (left, top, right, bottom)
    rc = placement[4]
    return [rc[0], rc[1], rc[2] - rc[0], rc[3] - rc[1]]


def capture_windows() -> list[dict[str, Any]]:
    """Enumerate all capturable windows and return their layout metadata.

    Returns a list of dicts with keys:
        hwnd     (int)   window handle
        title    (str)   window title
        exe      (str)   full path to executable
        rect     (list)  [left, top, width, height] — restore rect
        state    (str)   'normal' | 'maximized' | 'minimized'
    """
    windows: list[dict[str, Any]] = []

    def _cb(hwnd: int, _: Any) -> bool:
        if not _is_capturable(hwnd):
            return True
        entry: dict[str, Any] = {
            "hwnd": hwnd,
            "title": win32gui.GetWindowText(hwnd),
            "exe": _get_exe(hwnd),
            "rect": _get_rect(hwnd),
            "state": _get_window_state(hwnd),
        }
        windows.append(entry)
        log.debug("Captured: %s (%s)", entry["title"], os.path.basename(entry["exe"]))
        return True

    win32gui.EnumWindows(_cb, None)
    log.info("Captured %d windows", len(windows))
    return windows
