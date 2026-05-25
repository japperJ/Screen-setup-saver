"""Profile payload builder for layout saves."""

from __future__ import annotations

import os
from typing import Any

import browser
import browser_runtime
import capture

# Browser executable basenames → browser name used in browser_tabs
_BROWSER_EXE_NAMES: dict[str, str] = {
    "chrome.exe": "chrome",
    "msedge.exe": "edge",
}

# Reverse of _BROWSER_EXE_NAMES: browser name → exe basename
_BROWSER_NAME_TO_EXE: dict[str, str] = {v: k for k, v in _BROWSER_EXE_NAMES.items()}


def _annotate_browser_window_urls(
    windows: list[dict[str, Any]],
    tabs_by_browser: dict[str, list[dict[str, str]]],
) -> None:
    """Add a 'url' field in-place to browser window entries using CDP title matching.

    For each window whose exe is a browser, look up the best-matching tab URL by
    comparing the window title against the tab titles reported by CDP.
    """
    for entry in windows:
        exe_basename = os.path.basename(entry.get("exe", "")).lower()
        browser_name = _BROWSER_EXE_NAMES.get(exe_basename)
        if not browser_name:
            continue
        tabs = tabs_by_browser.get(browser_name, [])
        url = browser.match_tab_url_by_title(entry.get("title", ""), tabs)
        if url:
            entry["url"] = url


def build_profile_payload(
    cfg: dict[str, Any],
    windows_filter: set[int] | None = None,
) -> dict[str, Any]:
    """Build a serializable profile payload from current desktop and browser state.

    Args:
        cfg: App configuration dict (debug ports etc.).
        windows_filter: Optional set of HWNDs to include. When None all captured
            windows are saved (existing behaviour). When provided only windows
            whose ``hwnd`` is in the set are saved, and browser tabs are filtered
            to only the browsers represented by those windows.
    """
    chrome_port = cfg.get("chrome_debug_port", 9222)
    edge_port = cfg.get("edge_debug_port", 9223)

    windows = capture.capture_windows()

    if windows_filter is not None:
        windows = [w for w in windows if w.get("hwnd") in windows_filter]

    # Capture tabs with titles so we can associate each URL with its browser window
    tabs_by_browser = browser.capture_browser_tabs_with_titles(
        chrome_port=chrome_port, edge_port=edge_port
    )
    _annotate_browser_window_urls(windows, tabs_by_browser)

    # When a filter is active, drop tabs for browsers not represented in the selection
    if windows_filter is not None:
        selected_exes = {os.path.basename(w.get("exe", "")).lower() for w in windows}
        tabs_by_browser = {
            browser_name: tabs
            for browser_name, tabs in tabs_by_browser.items()
            if _BROWSER_NAME_TO_EXE.get(browser_name, "") in selected_exes
        }

    # Flat URL lists for legacy fallback restoration
    browser_tabs = {
        k: [t["url"] for t in tabs] for k, tabs in tabs_by_browser.items()
    }

    browser_exes: dict[str, str] = {}
    chrome_exe = browser_runtime.find_browser_exe("chrome")
    edge_exe = browser_runtime.find_browser_exe("edge")
    if chrome_exe:
        browser_exes["chrome"] = chrome_exe
    if edge_exe:
        browser_exes["edge"] = edge_exe

    return {
        "windows": windows,
        "browser_tabs": browser_tabs,
        "browser_exes": browser_exes,
        "browser_debug_ports": {
            "chrome.exe": chrome_port,
            "msedge.exe": edge_port,
        },
    }
