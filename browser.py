"""Browser tab capture via Chrome DevTools Protocol (CDP) HTTP endpoint."""

from __future__ import annotations

import json
import logging
import urllib.request
from urllib.parse import urlparse
from typing import Any

log = logging.getLogger(__name__)

# Default debug ports — overridable via config
CHROME_PORT = 9222
EDGE_PORT = 9223


def _fetch_tabs(port: int) -> list[dict[str, Any]]:
    """GET http://localhost:{port}/json/list and return parsed JSON, or [] on error."""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json/list", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception as exc:
        log.debug("CDP fetch failed on port %d: %s", port, exc)
        return []


def _extract_page_tabs_with_titles(raw: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Filter to page tabs and return [{title, url}] for restorable web URLs (http/https)."""
    tabs = []
    for entry in raw:
        if entry.get("type") != "page":
            continue
        url = entry.get("url", "")
        if urlparse(url).scheme.lower() not in {"http", "https"}:
            continue
        title = entry.get("title", "").strip()
        if title and url:
            tabs.append({"title": title, "url": url})
    return tabs


def _extract_page_tabs(raw: list[dict[str, Any]]) -> list[str]:
    """Filter to page tabs and keep only restorable web URLs (http/https)."""
    return [
        entry["url"] for entry in raw
        if entry.get("type") == "page"
        and urlparse(entry.get("url", "")).scheme.lower() in {"http", "https"}
    ]


def match_tab_url_by_title(window_title: str, tabs: list[dict[str, str]]) -> str | None:
    """Find the tab URL whose title best matches the start of window_title.

    Browser window titles follow the pattern "{active tab title} - {browser suffix}",
    so we find the longest tab title that is a prefix of window_title (case-insensitive).
    """
    window_lower = window_title.lower()
    best_url: str | None = None
    best_len = 0
    for tab in tabs:
        tab_title = tab.get("title", "").lower()
        if tab_title and window_lower.startswith(tab_title) and len(tab_title) > best_len:
            best_url = tab["url"]
            best_len = len(tab_title)
    return best_url


def capture_browser_tabs_with_titles(
    chrome_port: int = CHROME_PORT,
    edge_port: int = EDGE_PORT,
) -> dict[str, list[dict[str, str]]]:
    """Capture open tabs with titles from Chrome and Edge.

    Returns:
        {
            "chrome": [{"title": "...", "url": "https://..."}, ...],
            "edge":   [{"title": "...", "url": "https://..."}, ...],
        }
    Both lists may be empty if the browser isn't running or not in debug mode.
    """
    return {
        "chrome": _extract_page_tabs_with_titles(_fetch_tabs(chrome_port)),
        "edge": _extract_page_tabs_with_titles(_fetch_tabs(edge_port)),
    }


def capture_browser_tabs(
    chrome_port: int = CHROME_PORT,
    edge_port: int = EDGE_PORT,
) -> dict[str, list[str]]:
    """Capture open tabs from Chrome and Edge.

    Returns:
        {
            "chrome": ["https://...", ...],
            "edge":   ["https://...", ...],
        }
    Both lists may be empty if the browser isn't running or not in debug mode.
    """
    result = capture_browser_tabs_with_titles(chrome_port, edge_port)
    urls = {k: [t["url"] for t in tabs] for k, tabs in result.items()}
    log.info("Captured %d Chrome tabs, %d Edge tabs", len(urls["chrome"]), len(urls["edge"]))
    return urls

