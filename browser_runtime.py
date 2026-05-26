"""Runtime helpers for browser capture setup and status checks."""

from __future__ import annotations

import os
import subprocess
import urllib.request

import browser

_BROWSER_EXES: dict[str, list[str]] = {
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


def find_browser_exe(browser_name: str) -> str | None:
    """Return the first existing executable path for Chrome or Edge."""
    for path in _BROWSER_EXES.get(browser_name.lower(), []):
        if os.path.isfile(path):
            return path
    return None


def launch_browser_capture_mode(
    browser_name: str,
    port: int,
    address: str = "127.0.0.1",
) -> subprocess.Popen[bytes]:
    """Launch a browser with remote debugging enabled for tab capture."""
    exe = find_browser_exe(browser_name)
    if not exe:
        raise FileNotFoundError(f"{browser_name} executable not found")
    return subprocess.Popen(
        [
            exe,
            f"--remote-debugging-port={port}",
            f"--remote-debugging-address={address}",
        ]
    )


def _probe_port(port: int) -> bool:
    """Return True if CDP /json/version responds on localhost for the given port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
            return True
    except Exception:
        return False


def get_capture_status(chrome_port: int, edge_port: int) -> dict[str, dict]:
    """Return capture connectivity and URL counts for Chrome and Edge."""
    tabs = browser.capture_browser_tabs(chrome_port=chrome_port, edge_port=edge_port)
    return {
        "chrome": {
            "connected": _probe_port(chrome_port),
            "count": len(tabs.get("chrome", [])),
        },
        "edge": {
            "connected": _probe_port(edge_port),
            "count": len(tabs.get("edge", [])),
        },
    }
