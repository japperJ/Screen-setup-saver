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


def build_profile_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    """Build a serializable profile payload from current desktop and browser state."""
    chrome_port = cfg.get("chrome_debug_port", 9222)
    edge_port = cfg.get("edge_debug_port", 9223)

    windows = capture.capture_windows()

    # Capture tabs with titles so we can associate each URL with its browser window
    tabs_by_browser = browser.capture_browser_tabs_with_titles(
        chrome_port=chrome_port, edge_port=edge_port
    )
    _annotate_browser_window_urls(windows, tabs_by_browser)

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
