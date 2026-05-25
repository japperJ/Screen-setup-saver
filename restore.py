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

_POLL_INTERVAL       = 0.25  # seconds between window-search retries
_POLL_TIMEOUT        = 5.0   # max seconds to wait for a newly launched window
_STARTUP_DELAY       = 0.5   # seconds to let app settle before first placement attempt
_PLACE_RETRIES       = 5     # attempts to place the window
_PLACE_DELAY         = 0.5   # seconds between placement retries on API failure
_PLACE_VERIFY_TIMEOUT = 0.5  # seconds to wait for placement to be confirmed


# ── Window lookup ────────────────────────────────────────────────────────────

def _find_windows_by_exe(exe_path: str) -> list[int]:
    """Return user-facing HWNDs whose process executable matches exe_path (case-insensitive).

    Filters out transient startup windows (empty title, tool windows) to match
    the same eligibility rules as capture.py — preventing false hwnd assignments
    during browser startup where auxiliary windows appear before the real window.
    """
    exe_norm = exe_path.lower()
    results: list[int] = []

    def _cb(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        # Skip windows without a title — transient startup/helper windows have none
        if not win32gui.GetWindowText(hwnd).strip():
            return True
        # Skip tool windows (tooltips, floating toolbars, internal browser helpers)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
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


def _pick_hwnd(existing: list[int], saved_hwnd: int | None, assigned: set[int]) -> int | None:
    """Pick the best hwnd from existing windows.

    Preference order:
    1. The saved hwnd (exact match) if it's still in the list and not yet assigned
    2. First unassigned hwnd from the list
    3. None if all candidates are already assigned
    """
    if saved_hwnd and saved_hwnd in existing and saved_hwnd not in assigned:
        return saved_hwnd
    for hwnd in existing:
        if hwnd not in assigned:
            return hwnd
    return None


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

    After each placement attempt, polls until GetWindowRect/GetWindowPlacement
    confirms the position took effect — handles apps whose startup code fights
    placement by re-trying until the window actually stays where we put it.

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

        except Exception as exc:
            log.warning("Placement API call failed (attempt %d): %s", attempt + 1, exc)
            if attempt < _PLACE_RETRIES - 1:
                time.sleep(_PLACE_DELAY)
            continue

        # Condition-based verification: poll until placement confirms or timeout.
        # Avoids the race where the app's own startup/layout code overrides our placement.
        deadline = time.monotonic() + _PLACE_VERIFY_TIMEOUT
        confirmed = False
        while time.monotonic() < deadline:
            time.sleep(0.1)
            try:
                if state == "maximized":
                    placement = win32gui.GetWindowPlacement(hwnd)
                    if placement[1] == win32con.SW_SHOWMAXIMIZED:
                        confirmed = True
                        break
                else:
                    actual = win32gui.GetWindowRect(hwnd)
                    log.debug(
                        "RESTORE hwnd=%d  wanted=(%d,%d,%d,%d)  actual=%s",
                        hwnd, left, top, left + w, top + h, actual,
                    )
                    if abs(actual[0] - left) <= 2 and abs(actual[1] - top) <= 2:
                        confirmed = True
                        break
            except Exception:
                break

        if confirmed:
            log.debug("Placed hwnd=%d rect=%s state=%s (attempt %d)", hwnd, rect, state, attempt + 1)
            return

        log.debug("Placement not confirmed on attempt %d, retrying", attempt + 1)

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

_BROWSER_PROCESS_NAMES = {
    "chrome": {"chrome.exe"},
    "edge": {"msedge.exe"},
}

# Default debug ports per browser exe — keeps restored browsers debuggable for future saves
_BROWSER_DEFAULT_DEBUG_PORTS: dict[str, int] = {
    "chrome.exe": 9222,
    "msedge.exe": 9223,
}


def _find_browser_exe(browser_name: str) -> str | None:
    """Return the first found executable path for the named browser, or None."""
    for path in _BROWSER_EXES.get(browser_name, []):
        if os.path.isfile(path):
            return path
    return None


def _find_running_browser_exe(browser_name: str) -> str | None:
    """Return executable path from a visible running browser window, if any."""
    process_names = _BROWSER_PROCESS_NAMES.get(browser_name, set())
    if not process_names:
        return None

    found_paths: list[str] = []

    def _cb(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
            finally:
                win32api.CloseHandle(handle)
            if os.path.basename(exe_path).lower() in process_names and _is_restorable_exe(exe_path):
                found_paths.append(exe_path)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_cb, None)
    return found_paths[0] if found_paths else None


def _is_restorable_url(url: str) -> bool:
    """Allow only standard web URLs from profile data."""
    return urlparse(url).scheme in {"http", "https"}


def _is_restorable_exe(exe_path: str) -> bool:
    """Allow only absolute .exe paths that currently exist on disk."""
    return os.path.isabs(exe_path) and exe_path.lower().endswith(".exe") and os.path.isfile(exe_path)


def _resolve_browser_exe(browser_name: str, browser_exes: dict[str, str] | None = None) -> str | None:
    """Resolve browser executable with priority: hint, detected install, running browser."""
    hints = browser_exes or {}

    hinted_exe = hints.get(browser_name)
    if hinted_exe and _is_restorable_exe(hinted_exe):
        return hinted_exe

    detected_exe = _find_browser_exe(browser_name)
    if detected_exe and _is_restorable_exe(detected_exe):
        return detected_exe

    return _find_running_browser_exe(browser_name)


def restore_browser_tabs(
    browser_tabs: dict[str, list[str]],
    browser_exes: dict[str, str] | None = None,
    skip_urls: set[str] | None = None,
) -> None:
    """Open saved browser tabs in the correct browser.

    skip_urls: URLs already opened via per-window launch; omit them to avoid duplicates.
    """
    skip = skip_urls or set()
    for browser_name, urls in browser_tabs.items():
        if not urls:
            continue
        exe = _resolve_browser_exe(browser_name, browser_exes)
        for url in urls:
            if url in skip:
                log.debug("Skipping already-opened URL for %s: %s", browser_name, url)
                continue
            if not _is_restorable_url(url):
                log.warning("Skipping non-web URL for %s: %s", browser_name, url)
                continue
            try:
                if exe:
                    subprocess.Popen([exe, url])
                    log.debug("Opened %s tab via exe: %s", browser_name, url)
                else:
                    log.warning(
                        "Executable for %s not resolved; opening URL via default browser: %s",
                        browser_name,
                        url,
                    )
                    webbrowser.open(url)
            except Exception as exc:
                log.warning("Failed to open URL %s: %s", url, exc)


# ── Main restore entry point ──────────────────────────────────────────────────

def restore_profile(profile: dict[str, Any]) -> None:
    """Restore a saved profile: relaunch apps, reposition windows, reopen browser tabs.

    profile keys:
        windows             list of window dicts (title, exe, rect, state[, url])
        browser_tabs        dict  {"chrome": [...urls], "edge": [...urls]}
        browser_exes        dict  {"chrome": "path\\to\\chrome.exe", ...}
        browser_debug_ports dict  {"chrome.exe": 9222, "msedge.exe": 9223}  (optional)
    """
    windows: list[dict[str, Any]] = profile.get("windows", [])
    browser_tabs: dict[str, list[str]] = profile.get("browser_tabs", {})
    browser_exes: dict[str, str] = profile.get("browser_exes", {})
    # Per-exe debug ports stored at save time; fall back to built-in defaults
    browser_debug_ports: dict[str, int] = {
        **_BROWSER_DEFAULT_DEBUG_PORTS,
        **profile.get("browser_debug_ports", {}),
    }

    assigned_hwnds: set[int] = set()  # prevent two saved entries from grabbing same window
    opened_window_urls: set[str] = set()  # URLs handled per-window; skip in browser_tabs

    for entry in windows:
        exe = entry.get("exe", "")
        rect = entry.get("rect", [0, 0, 800, 600])
        state = entry.get("state", "normal")
        title = entry.get("title", "")
        saved_hwnd: int | None = entry.get("hwnd")
        window_url: str = entry.get("url", "")  # per-window URL (new field, may be absent)

        if not exe or not _is_restorable_exe(exe):
            log.warning("Skipping %r — unsafe or missing exe path: %s", title, exe)
            continue

        existing = _find_windows_by_exe(exe)
        known_hwnds = set(existing)

        # Reposition an unassigned running window when available.
        # If all running windows are already used for earlier saved entries, launch another instance.
        if existing:
            hwnd = _pick_hwnd(existing, saved_hwnd, assigned_hwnds)
            if hwnd is not None:
                assigned_hwnds.add(hwnd)
                log.info("App already running (%s), repositioning existing window hwnd=%d", os.path.basename(exe), hwnd)
                _apply_placement(hwnd, rect, state)
                # Window is already open at its current URL; mark URL as handled
                if window_url and _is_restorable_url(window_url):
                    opened_window_urls.add(window_url)
                continue

        # App not running (or all existing windows are assigned) — launch a new instance.
        # Add --remote-debugging-port only when this is a truly fresh start (no existing windows).
        # If the browser is already running (all windows were assigned), it already owns the debug
        # port; passing --remote-debugging-port to the relay command conflicts with the bound port
        # and prevents --new-window from opening a second window reliably.
        exe_basename = os.path.basename(exe).lower()
        debug_port: int | None = browser_debug_ports.get(exe_basename)
        browser_is_fresh_start = not existing  # existing is [] when browser wasn't running at all
        debug_args = (
            [f"--remote-debugging-port={debug_port}", "--remote-debugging-address=127.0.0.1"]
            if debug_port and browser_is_fresh_start else []
        )

        try:
            if window_url and _is_restorable_url(window_url):
                # Use --new-window to force a separate browser window (not a tab in an existing one)
                subprocess.Popen([exe, "--new-window", window_url] + debug_args)
                opened_window_urls.add(window_url)
                log.info("Launched %s with --new-window %s (debug port %s)", exe, window_url, debug_port if browser_is_fresh_start else "inherited")
            else:
                subprocess.Popen([exe] + debug_args)
                log.info("Launched %s (debug port %s)", exe, debug_port if browser_is_fresh_start else "inherited")
        except Exception as exc:
            log.error("Failed to launch %s: %s", exe, exc)
            continue

        hwnd = _wait_for_window(exe, known_hwnds)
        if hwnd is None:
            log.warning("Window for %s did not appear within %.1fs", exe, _POLL_TIMEOUT)
            continue

        assigned_hwnds.add(hwnd)  # prevent a later entry from reusing this newly launched window
        # Give the app time to finish initializing before we force its position,
        # otherwise the app's own startup code may override our placement.
        time.sleep(_STARTUP_DELAY)
        _apply_placement(hwnd, rect, state)

    if browser_tabs:
        restore_browser_tabs(browser_tabs, browser_exes, skip_urls=opened_window_urls)
