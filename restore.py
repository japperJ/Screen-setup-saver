"""Profile restoration — relaunch apps, reposition windows, reopen browser tabs."""

from __future__ import annotations

import logging
import os
import subprocess
import time
import webbrowser
from typing import Any
from urllib.parse import urlparse

import win32api
import win32con
import win32gui
import win32process

log = logging.getLogger(__name__)

_POLL_INTERVAL  = 0.25  # seconds between window-search retries
_POLL_TIMEOUT   = 5.0   # max seconds to wait for a newly launched window
_STARTUP_DELAY  = 1.5   # seconds to wait after a new window appears before placing it
_PLACE_RETRIES  = 3     # attempts to place the window
_PLACE_DELAY    = 0.5   # seconds between placement retries


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


def _pick_hwnd(existing: list[int], saved_hwnd: int | None, assigned: set[int]) -> int:
    """Pick the best hwnd from existing windows.

    Preference order:
    1. The saved hwnd (exact match) if it's still in the list and not yet assigned
    2. First unassigned hwnd from the list
    3. existing[0] as last resort
    """
    if saved_hwnd and saved_hwnd in existing and saved_hwnd not in assigned:
        return saved_hwnd
    for hwnd in existing:
        if hwnd not in assigned:
            return hwnd
    return existing[0]


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
    """Set window position/size/state reliably. Retries up to _PLACE_RETRIES times.

    Both rect (from GetWindowRect) and SetWindowPos use screen coordinates —
    consistent coordinate system, no workspace-vs-screen mismatch.
    """
    left, top, w, h = rect

    swp_flags = win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER

    for attempt in range(_PLACE_RETRIES):
        try:
            # Step 1: un-minimize / un-maximize so window can be freely moved
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Step 2: force exact screen position and size
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, left, top, w, h, swp_flags)

            # Step 3: re-apply maximized state if needed (SetWindowPos normalised it)
            if state == "maximized":
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

            log.debug("Placed hwnd=%d rect=%s state=%s (attempt %d)", hwnd, rect, state, attempt + 1)

            # Diagnostic: verify actual position after placement
            try:
                import time as _time
                _time.sleep(0.2)
                actual = win32gui.GetWindowRect(hwnd)
                log.debug(
                    "RESTORE hwnd=%d  wanted=(%d,%d,%d,%d)  actual=%s",
                    hwnd, left, top, left+w, top+h, actual
                )
            except Exception:
                pass

            return
        except Exception as exc:
            log.warning("Placement failed (attempt %d): %s", attempt + 1, exc)
            if attempt < _PLACE_RETRIES - 1:
                time.sleep(_PLACE_DELAY)

    log.error("Failed to place hwnd=%d after %d attempts", hwnd, _PLACE_RETRIES)


# ── Browser tab restoration ───────────────────────────────────────────────────

_BROWSER_EXES = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
}


def _find_browser_exe(browser_name: str) -> str | None:
    """Return the first found executable path for the named browser, or None."""
    for path in _BROWSER_EXES.get(browser_name, []):
        if os.path.isfile(path):
            return path
    return None


def _is_restorable_url(url: str) -> bool:
    """Allow only standard web URLs from profile data."""
    return urlparse(url).scheme in {"http", "https"}


def _is_restorable_exe(exe_path: str) -> bool:
    """Allow only absolute .exe paths that currently exist on disk."""
    return os.path.isabs(exe_path) and exe_path.lower().endswith(".exe") and os.path.isfile(exe_path)


def restore_browser_tabs(browser_tabs: dict[str, list[str]]) -> None:
    """Open saved browser tabs in the correct browser."""
    for browser_name, urls in browser_tabs.items():
        if not urls:
            continue
        exe = _find_browser_exe(browser_name)
        for url in urls:
            if not _is_restorable_url(url):
                log.warning("Skipping non-web URL for %s: %s", browser_name, url)
                continue
            try:
                if exe:
                    subprocess.Popen([exe, url])
                    log.debug("Opened %s tab via exe: %s", browser_name, url)
                else:
                    webbrowser.open(url)
                    log.debug("Opened %s tab via webbrowser (exe not found): %s", browser_name, url)
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

    assigned_hwnds: set[int] = set()  # prevent two saved entries from grabbing same window

    for entry in windows:
        exe = entry.get("exe", "")
        rect = entry.get("rect", [0, 0, 800, 600])
        state = entry.get("state", "normal")
        title = entry.get("title", "")
        saved_hwnd: int | None = entry.get("hwnd")

        if not exe or not _is_restorable_exe(exe):
            log.warning("Skipping %r — unsafe or missing exe path: %s", title, exe)
            continue

        # If app is already running, reposition its existing window instead of launching a new instance
        existing = _find_windows_by_exe(exe)
        if existing:
            hwnd = _pick_hwnd(existing, saved_hwnd, assigned_hwnds)
            assigned_hwnds.add(hwnd)
            log.info("App already running (%s), repositioning existing window hwnd=%d", os.path.basename(exe), hwnd)
            _apply_placement(hwnd, rect, state)
            continue

        # App not running — launch it and wait for its window to appear
        try:
            # Security: never execute argument vectors from profile JSON.
            # Only launch the resolved executable path.
            subprocess.Popen([exe])
            log.info("Launched %s", exe)
        except Exception as exc:
            log.error("Failed to launch %s: %s", exe, exc)
            continue

        hwnd = _wait_for_window(exe, set())
        if hwnd is None:
            log.warning("Window for %s did not appear within %.1fs", exe, _POLL_TIMEOUT)
            continue

        # Give the app time to finish initializing before we force its position,
        # otherwise the app's own startup code may override our placement.
        time.sleep(_STARTUP_DELAY)
        _apply_placement(hwnd, rect, state)

    if browser_tabs:
        restore_browser_tabs(browser_tabs)
