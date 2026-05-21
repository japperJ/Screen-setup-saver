"""Browser tab capture via Chrome DevTools Protocol (CDP) HTTP endpoint."""

from __future__ import annotations

import logging
import urllib.request
import json
from typing import Any

log = logging.getLogger(__name__)

# Default debug ports — overridable via config
CHROME_PORT = 9222
EDGE_PORT = 9223


def _fetch_tabs(port: int) -> list[dict[str, Any]]:
    """GET http://localhost:{port}/json/list and return parsed JSON, or [] on error."""
    url = f"http://localhost:{port}/json/list"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception as exc:
        log.debug("CDP fetch failed on port %d: %s", port, exc)
        return []


def _extract_page_tabs(raw: list[dict[str, Any]]) -> list[str]:
    """Filter to 'page' type entries and return their URLs, skipping chrome:// and edge:// internals."""
    urls = []
    for entry in raw:
        if entry.get("type") != "page":
            continue
        url = entry.get("url", "")
        if url.startswith(("chrome://", "edge://", "chrome-extension://", "about:")):
            continue
        if url:
            urls.append(url)
    return urls


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
    chrome_raw = _fetch_tabs(chrome_port)
    edge_raw = _fetch_tabs(edge_port)

    result = {
        "chrome": _extract_page_tabs(chrome_raw),
        "edge": _extract_page_tabs(edge_raw),
    }
    log.info(
        "Captured %d Chrome tabs, %d Edge tabs",
        len(result["chrome"]),
        len(result["edge"]),
    )
    return result
