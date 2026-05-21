"""Profile restoration — relaunch apps, reposition windows, reopen browser tabs."""

from __future__ import annotations

import logging
import os
import subprocess
import time
import webbrowser
from typing import Any

import win32api
import win32con
import win32gui
import win32process

log = logging.getLogger(__name__)

_POLL_INTERVAL = 0.25   # seconds between window-search retries
_POLL_TIMEOUT  = 5.0    # max seconds to wait for a newly launched window
_PLACE_RETRIES = 3      # attempts to SetWindowPlacement
_PLACE_DELAY   = 0.5    # seconds between placement retries


# ── Window lookup ────────────────────────────────────────────────────────────

def _find_windows_by_exe(exe_path: str) -> list[int]:
    """Return all visible HWNDs whose process executable matches exe_path (case-insensitive)."""
    exe_norm = exe_path.lower()
    results: list[int] = []

    def _cb(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                path = win32process.GetModuleFileNameEx(handle, 0)
            finally:
                win32api.CloseHandle(handle)
            if path.lower() == exe_norm:
                results.append(hwnd)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_cb, None)
    return results


def _wait_for_window(exe_path: str, known_hwnds: set[int], timeout: float = _POLL_TIMEOUT) -> int | None:
    """Poll until a NEW hwnd appears for exe_path (not in known_hwnds). Returns hwnd or None."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for hwnd in _find_windows_by_exe(exe_path):
            if hwnd not in known_hwnds:
                return hwnd
        time.sleep(_POLL_INTERVAL)
    return None


# ── Window placement ─────────────────────────────────────────────────────────

def _apply_placement(hwnd: int, rect: list[int], state: str) -> None:
    """Set window position/size/state. Retries up to _PLACE_RETRIES times."""
    left, top, w, h = rect
    right, bottom = left + w, top + h

    if state == "maximized":
        show_cmd = win32con.SW_SHOWMAXIMIZED
    elif state == "minimized":
        show_cmd = win32con.SW_SHOWMINIMIZED
    else:
        show_cmd = win32con.SW_SHOWNORMAL

    placement = (0, show_cmd, (0, 0), (0, 0), (left, top, right, bottom))

    for attempt in range(_PLACE_RETRIES):
        try:
            win32gui.SetWindowPlacement(hwnd, placement)
            log.debug("Placed hwnd=%d rect=%s state=%s (attempt %d)", hwnd, rect, state, attempt + 1)
            return
        except Exception as exc:
            log.warning("SetWindowPlacement failed (attempt %d): %s", attempt + 1, exc)
            if attempt < _PLACE_RETRIES - 1:
                time.sleep(_PLACE_DELAY)

    log.error("Failed to place hwnd=%d after %d attempts", hwnd, _PLACE_RETRIES)


# ── Browser tab restoration ───────────────────────────────────────────────────

def restore_browser_tabs(browser_tabs: dict[str, list[str]]) -> None:
    """Open saved browser tabs using the system default browser handler."""
    for browser_name, urls in browser_tabs.items():
        for url in urls:
            try:
                webbrowser.open(url)
                log.debug("Opened %s tab: %s", browser_name, url)
            except Exception as exc:
                log.warning("Failed to open URL %s: %s", url, exc)


# ── Main restore entry point ──────────────────────────────────────────────────

def restore_profile(profile: dict[str, Any]) -> None:
    """Restore a saved profile: relaunch apps, reposition windows, reopen browser tabs.

    profile keys:
        windows      list of window dicts (title, exe, rect, state)
        browser_tabs dict  {"chrome": [...urls], "edge": [...urls]}
    """
    windows: list[dict[str, Any]] = profile.get("windows", [])
    browser_tabs: dict[str, list[str]] = profile.get("browser_tabs", {})

    for entry in windows:
        exe = entry.get("exe", "")
        rect = entry.get("rect", [0, 0, 800, 600])
        state = entry.get("state", "normal")
        title = entry.get("title", "")

        if not exe or not os.path.isfile(exe):
            log.warning("Skipping %r — exe not found: %s", title, exe)
            continue

        # Remember existing windows for this exe so we can detect the NEW one
        known = set(_find_windows_by_exe(exe))

        try:
            subprocess.Popen([exe])
            log.info("Launched %s", exe)
        except Exception as exc:
            log.error("Failed to launch %s: %s", exe, exc)
            continue

        hwnd = _wait_for_window(exe, known)
        if hwnd is None:
            log.warning("Window for %s did not appear within %.1fs", exe, _POLL_TIMEOUT)
            continue

        _apply_placement(hwnd, rect, state)

    if browser_tabs:
        restore_browser_tabs(browser_tabs)
