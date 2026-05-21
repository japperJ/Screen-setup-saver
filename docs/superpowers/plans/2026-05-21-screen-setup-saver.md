# Screen Setup Saver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows 11 system tray utility that saves/restores window layouts and browser tabs across multiple named profiles with configurable global hotkeys.

**Architecture:** A Python app with 8 focused modules wired together in `main.py`. The tray icon (pystray) runs in a daemon thread while a hidden tkinter root keeps the main thread alive for the settings window. Window state is captured via pywin32/psutil; browser tabs via Chrome DevTools Protocol HTTP endpoint; profiles persisted as JSON in `%APPDATA%\ScreenSetupSaver\`.

**Tech Stack:** Python 3.11+, pywin32, pystray, keyboard, Pillow, psutil — all installable via pip. tkinter is built into Python.

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | Entry point — init all modules, wire callbacks, start tray + tkinter loop |
| `profiles.py` | Load/save/list/delete/rename profiles and config from `%APPDATA%` |
| `capture.py` | Enumerate visible windows via win32gui; return title/exe/rect/state |
| `browser.py` | HTTP GET to CDP `/json/list`; return open tab URLs for Chrome/Edge |
| `restore.py` | Launch apps, poll for window handle, reposition; open browser with tabs |
| `hotkeys.py` | Register/unregister global hotkeys via `keyboard` library |
| `tray.py` | pystray Icon with dynamic right-click menu |
| `settings_ui.py` | tkinter Toplevel with Profiles, Hotkeys, Browser Setup tabs |
| `assets/icon.png` | Tray icon; auto-generated at runtime if missing |
| `requirements.txt` | Pinned dependencies |
| `run.bat` | Double-click launcher |
| `tests/test_profiles.py` | Unit tests for profiles.py |
| `tests/test_capture.py` | Unit tests for capture.py (win32gui mocked) |
| `tests/test_browser.py` | Unit tests for browser.py (urllib mocked) |
| `tests/test_restore.py` | Unit tests for restore.py (win32gui + subprocess mocked) |
| `tests/test_hotkeys.py` | Unit tests for hotkeys.py (keyboard mocked) |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `run.bat`
- Create: `assets/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
pywin32==308
pystray==0.19.5
keyboard==0.13.5
Pillow==10.3.0
psutil==5.9.8
pytest==8.2.0
```

- [ ] **Step 2: Create `run.bat`**

```bat
@echo off
cd /d "%~dp0"
python main.py
pause
```

- [ ] **Step 3: Create `assets/.gitkeep`**

```
(empty file)
```

- [ ] **Step 4: Create `tests/__init__.py`**

```python
```

- [ ] **Step 5: Create `tests/conftest.py`**

```python
import sys
from unittest.mock import MagicMock

# Stub out Windows-only modules so tests can import app modules on any machine
for mod in [
    "win32gui", "win32process", "win32con", "win32api", "pystray", "keyboard",
]:
    sys.modules.setdefault(mod, MagicMock())
```

- [ ] **Step 6: Install dependencies**

```
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 7: Verify pytest works**

```
pytest tests/ -v
```

Expected: `no tests ran` (0 collected), exit 0.

- [ ] **Step 8: Commit**

```
git add requirements.txt run.bat assets/.gitkeep tests/
git commit -m "chore: project scaffold with dependencies and test harness"
```

---

## Task 2: `profiles.py` — Profile & Config I/O

**Files:**
- Create: `profiles.py`
- Create: `tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_profiles.py`:

```python
import json
import os
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def tmp_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # Force module to re-resolve APP_DIR on each test
    import importlib
    import profiles
    importlib.reload(profiles)
    return tmp_path


def test_load_config_returns_defaults_when_missing():
    import profiles
    config = profiles.load_config()
    assert config["hotkeys"]["save"] == "ctrl+alt+s"
    assert config["hotkeys"]["restore_last"] == "ctrl+alt+r"
    assert config["hotkeys"]["open_settings"] == "ctrl+alt+w"
    assert config["last_profile"] is None


def test_save_and_load_config(tmp_path):
    import profiles
    cfg = profiles.load_config()
    cfg["last_profile"] = "Work Setup"
    profiles.save_config(cfg)
    loaded = profiles.load_config()
    assert loaded["last_profile"] == "Work Setup"


def test_save_and_load_profile():
    import profiles
    p = {
        "name": "Work Setup",
        "saved_at": "2026-05-21T10:00:00",
        "windows": [{"title": "VSCode", "exe": "code.exe", "rect": [0, 0, 1920, 1080], "state": "maximized"}],
        "browsers": [],
    }
    profiles.save_profile(p)
    loaded = profiles.load_profile("Work Setup")
    assert loaded["name"] == "Work Setup"
    assert loaded["windows"][0]["title"] == "VSCode"


def test_list_profiles_sorted_by_date():
    import profiles
    profiles.save_profile({"name": "A", "saved_at": "2026-05-20T10:00:00", "windows": [], "browsers": []})
    profiles.save_profile({"name": "B", "saved_at": "2026-05-21T10:00:00", "windows": [], "browsers": []})
    result = profiles.list_profiles()
    assert result[0]["name"] == "B"
    assert result[1]["name"] == "A"


def test_delete_profile():
    import profiles
    profiles.save_profile({"name": "X", "saved_at": "2026-01-01", "windows": [], "browsers": []})
    assert profiles.delete_profile("X") is True
    assert profiles.load_profile("X") is None
    assert profiles.delete_profile("X") is False  # already gone


def test_rename_profile():
    import profiles
    profiles.save_profile({"name": "Old", "saved_at": "2026-01-01", "windows": [], "browsers": []})
    assert profiles.rename_profile("Old", "New") is True
    assert profiles.load_profile("New")["name"] == "New"
    assert profiles.load_profile("Old") is None


def test_list_profiles_skips_corrupted(tmp_path, monkeypatch):
    import profiles
    profiles.ensure_dirs()
    bad = profiles.PROFILES_DIR / "corrupt.json"
    bad.write_text("NOT JSON")
    result = profiles.list_profiles()
    assert all(isinstance(p, dict) for p in result)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_profiles.py -v
```

Expected: `ModuleNotFoundError: No module named 'profiles'`

- [ ] **Step 3: Create `profiles.py`**

```python
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

APP_DIR = Path(os.environ["APPDATA"]) / "ScreenSetupSaver"
PROFILES_DIR = APP_DIR / "profiles"
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "app.log"

DEFAULT_CONFIG = {
    "last_profile": None,
    "hotkeys": {
        "save": "ctrl+alt+s",
        "restore_last": "ctrl+alt+r",
        "open_settings": "ctrl+alt+w",
        "quick_restore": {},
    },
}


def ensure_dirs():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    if not CONFIG_FILE.exists():
        return {**DEFAULT_CONFIG, "hotkeys": {**DEFAULT_CONFIG["hotkeys"]}}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = {**DEFAULT_CONFIG, "hotkeys": {**DEFAULT_CONFIG["hotkeys"]}}
        merged.update({k: v for k, v in data.items() if k != "hotkeys"})
        merged["hotkeys"].update(data.get("hotkeys", {}))
        return merged
    except (json.JSONDecodeError, OSError):
        return {**DEFAULT_CONFIG, "hotkeys": {**DEFAULT_CONFIG["hotkeys"]}}


def save_config(config: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _profile_path(name: str) -> Path:
    safe = name.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_")
    return PROFILES_DIR / f"{safe}.json"


def save_profile(profile: dict):
    ensure_dirs()
    with open(_profile_path(profile["name"]), "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def load_profile(name: str) -> Optional[dict]:
    path = _profile_path(name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def list_profiles() -> list:
    ensure_dirs()
    results = []
    for p in PROFILES_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    results.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return results


def delete_profile(name: str) -> bool:
    path = _profile_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def rename_profile(old_name: str, new_name: str) -> bool:
    old_path = _profile_path(old_name)
    new_path = _profile_path(new_name)
    if not old_path.exists() or new_path.exists():
        return False
    data = load_profile(old_name)
    if data is None:
        return False
    data["name"] = new_name
    old_path.unlink()
    save_profile(data)
    return True


def log(message: str):
    ensure_dirs()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_profiles.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```
git add profiles.py tests/test_profiles.py
git commit -m "feat: profiles.py — load/save/list/delete/rename profiles and config"
```

---

## Task 3: `capture.py` — Window Enumeration

**Files:**
- Create: `capture.py`
- Create: `tests/test_capture.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_capture.py`:

```python
import sys
from unittest.mock import MagicMock, patch, call
import pytest


def _make_hwnd_setup(hwnds):
    """Helper: make EnumWindows call callback for each hwnd in hwnds."""
    def fake_enum(callback, param):
        for hwnd in hwnds:
            callback(hwnd, param)
    return fake_enum


def test_capture_skips_invisible_windows():
    import capture
    with patch("capture.win32gui") as gui, patch("capture.win32process") as proc, \
         patch("capture.psutil") as ps:
        gui.EnumWindows.side_effect = _make_hwnd_setup([1])
        gui.IsWindowVisible.return_value = False
        result = capture.capture_windows()
    assert result == []


def test_capture_skips_empty_title():
    import capture
    with patch("capture.win32gui") as gui, patch("capture.win32process") as proc, \
         patch("capture.psutil") as ps:
        gui.EnumWindows.side_effect = _make_hwnd_setup([1])
        gui.IsWindowVisible.return_value = True
        gui.GetWindowText.return_value = ""
        gui.GetWindowLong.return_value = 0
        gui.GetClassName.return_value = "SomeClass"
        result = capture.capture_windows()
    assert result == []


def test_capture_returns_window_dict():
    import capture
    with patch("capture.win32gui") as gui, patch("capture.win32process") as proc, \
         patch("capture.psutil") as ps:
        gui.EnumWindows.side_effect = _make_hwnd_setup([42])
        gui.IsWindowVisible.return_value = True
        gui.GetWindowText.return_value = "My App"
        gui.GetClassName.return_value = "AppClass"
        gui.GetWindowLong.return_value = 0  # no WS_EX_TOOLWINDOW
        gui.GetWindowRect.return_value = (100, 200, 1100, 900)
        gui.GetWindowPlacement.return_value = (0, 1, 0, (0,0), (100,200,1100,900))  # SW_SHOWNORMAL=1
        proc.GetWindowThreadProcessId.return_value = (0, 999)
        mock_proc = MagicMock()
        mock_proc.exe.return_value = r"C:\apps\myapp.exe"
        ps.Process.return_value = mock_proc

        import win32con
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2
        win32con.GWL_EXSTYLE = -20
        win32con.WS_EX_TOOLWINDOW = 0x00000080

        result = capture.capture_windows()

    assert len(result) == 1
    w = result[0]
    assert w["title"] == "My App"
    assert w["exe"] == r"C:\apps\myapp.exe"
    assert w["rect"] == [100, 200, 1000, 700]  # [left, top, width, height]
    assert w["state"] == "normal"


def test_capture_detects_maximized():
    import capture
    import win32con
    win32con.SW_SHOWMAXIMIZED = 3
    win32con.SW_SHOWMINIMIZED = 2
    win32con.GWL_EXSTYLE = -20
    win32con.WS_EX_TOOLWINDOW = 0x00000080

    with patch("capture.win32gui") as gui, patch("capture.win32process") as proc, \
         patch("capture.psutil") as ps:
        gui.EnumWindows.side_effect = _make_hwnd_setup([42])
        gui.IsWindowVisible.return_value = True
        gui.GetWindowText.return_value = "Editor"
        gui.GetClassName.return_value = "Edit"
        gui.GetWindowLong.return_value = 0
        gui.GetWindowRect.return_value = (0, 0, 1920, 1080)
        gui.GetWindowPlacement.return_value = (0, 3, 0, (0,0), (0,0,1920,1080))  # SW_SHOWMAXIMIZED=3
        proc.GetWindowThreadProcessId.return_value = (0, 1)
        mock_proc = MagicMock()
        mock_proc.exe.return_value = r"C:\editor.exe"
        ps.Process.return_value = mock_proc

        result = capture.capture_windows()

    assert result[0]["state"] == "maximized"


def test_split_windows_and_browsers():
    import capture
    windows = [
        {"title": "VSCode", "exe": r"C:\code.exe", "rect": [0,0,1920,1080], "state": "normal"},
        {"title": "Chrome", "exe": r"C:\chrome.exe", "rect": [0,0,1920,1080], "state": "normal"},
        {"title": "Edge", "exe": r"C:\msedge.exe", "rect": [0,0,1920,1080], "state": "normal"},
    ]
    regular, browsers = capture.split_windows(windows)
    assert len(regular) == 1
    assert regular[0]["title"] == "VSCode"
    assert len(browsers) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_capture.py -v
```

Expected: `ModuleNotFoundError: No module named 'capture'`

- [ ] **Step 3: Create `capture.py`**

```python
import win32gui
import win32process
import win32con
import psutil
from pathlib import Path
from typing import Optional

SKIP_TITLES = frozenset({"Program Manager", ""})
SKIP_CLASSES = frozenset({
    "Shell_TrayWnd", "DV2ControlHost", "MsgrIMEWindowClass",
    "SysShadow", "Button", "Windows.UI.Core.CoreWindow",
    "ApplicationFrameWindow",
})
BROWSER_EXES = frozenset({"chrome.exe", "msedge.exe"})


def _get_exe(hwnd: int) -> Optional[str]:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).exe()
    except Exception:
        return None


def _window_state(hwnd: int) -> str:
    placement = win32gui.GetWindowPlacement(hwnd)
    show_cmd = placement[1]
    if show_cmd == win32con.SW_SHOWMAXIMIZED:
        return "maximized"
    if show_cmd == win32con.SW_SHOWMINIMIZED:
        return "minimized"
    return "normal"


def _is_relevant(hwnd: int) -> bool:
    if not win32gui.IsWindowVisible(hwnd):
        return False
    title = win32gui.GetWindowText(hwnd)
    if title in SKIP_TITLES:
        return False
    class_name = win32gui.GetClassName(hwnd)
    if class_name in SKIP_CLASSES:
        return False
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False
    return True


def capture_windows() -> list:
    """Return list of window dicts for all relevant visible windows."""
    windows = []

    def callback(hwnd, _):
        if not _is_relevant(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        rect = [left, top, right - left, bottom - top]
        state = _window_state(hwnd)
        exe = _get_exe(hwnd)
        if exe is None:
            return True
        windows.append({"title": title, "exe": exe, "rect": rect, "state": state})
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def split_windows(windows: list) -> tuple:
    """Split window list into (regular_windows, browser_windows)."""
    regular = [w for w in windows if Path(w["exe"]).name.lower() not in BROWSER_EXES]
    browsers = [w for w in windows if Path(w["exe"]).name.lower() in BROWSER_EXES]
    return regular, browsers
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_capture.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add capture.py tests/test_capture.py
git commit -m "feat: capture.py — enumerate windows with title/exe/rect/state"
```

---

## Task 4: `browser.py` — CDP Tab Listing

**Files:**
- Create: `browser.py`
- Create: `tests/test_browser.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_browser.py`:

```python
import json
from unittest.mock import patch, MagicMock
import io


def _mock_urlopen(data: list):
    response = MagicMock()
    response.read.return_value = json.dumps(data).encode()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    return response


def test_get_tabs_returns_page_urls():
    import browser
    targets = [
        {"type": "page", "url": "https://github.com", "title": "GitHub"},
        {"type": "page", "url": "https://python.org", "title": "Python"},
        {"type": "service_worker", "url": "chrome-extension://abc", "title": ""},
    ]
    with patch("browser.urllib.request.urlopen", return_value=_mock_urlopen(targets)):
        result = browser.get_tabs("chrome")
    assert result == ["https://github.com", "https://python.org"]


def test_get_tabs_excludes_non_http():
    import browser
    targets = [
        {"type": "page", "url": "chrome://newtab/", "title": "New Tab"},
        {"type": "page", "url": "https://example.com", "title": "Example"},
    ]
    with patch("browser.urllib.request.urlopen", return_value=_mock_urlopen(targets)):
        result = browser.get_tabs("edge")
    assert result == ["https://example.com"]


def test_get_tabs_returns_empty_on_connection_error():
    import browser
    with patch("browser.urllib.request.urlopen", side_effect=OSError("refused")):
        result = browser.get_tabs("chrome")
    assert result == []


def test_get_tabs_unknown_browser_returns_empty():
    import browser
    result = browser.get_tabs("firefox")
    assert result == []


def test_is_connected_true_when_reachable():
    import browser
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("browser.urllib.request.urlopen", return_value=mock_resp):
        assert browser.is_connected("chrome") is True


def test_is_connected_false_when_unreachable():
    import browser
    with patch("browser.urllib.request.urlopen", side_effect=OSError):
        assert browser.is_connected("chrome") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_browser.py -v
```

Expected: `ModuleNotFoundError: No module named 'browser'`

- [ ] **Step 3: Create `browser.py`**

```python
import urllib.request
import json
from typing import Optional

CDP_PORTS = {
    "chrome": 9222,
    "edge": 9223,
}


def get_tabs(browser: str) -> list:
    """Return list of HTTP tab URLs for the given browser.
    Returns empty list if browser is not reachable on its debug port.
    """
    port = CDP_PORTS.get(browser)
    if port is None:
        return []
    try:
        url = f"http://localhost:{port}/json/list"
        with urllib.request.urlopen(url, timeout=2) as resp:
            targets = json.loads(resp.read().decode())
        return [
            t["url"]
            for t in targets
            if t.get("type") == "page" and t.get("url", "").startswith("http")
        ]
    except Exception:
        return []


def is_connected(browser: str) -> bool:
    """Return True if the browser is running with its debug port open."""
    port = CDP_PORTS.get(browser)
    if port is None:
        return False
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=1):
            return True
    except Exception:
        return False


BROWSER_EXES = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
}

DEBUG_PORT_FLAGS = {
    "chrome": "--remote-debugging-port=9222",
    "edge": "--remote-debugging-port=9223",
}
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_browser.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add browser.py tests/test_browser.py
git commit -m "feat: browser.py — CDP tab listing for Chrome and Edge"
```

---

## Task 5: `restore.py` — Launch Apps and Reposition Windows

**Files:**
- Create: `restore.py`
- Create: `tests/test_restore.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_restore.py`:

```python
from unittest.mock import patch, MagicMock, call
import pytest


def test_set_window_geometry_normal():
    import restore
    import win32con
    win32con.SW_RESTORE = 9
    win32con.HWND_TOP = 0
    win32con.SWP_NOZORDER = 4
    win32con.SW_MAXIMIZE = 3
    win32con.SW_MINIMIZE = 6

    with patch("restore.win32gui") as gui:
        restore._set_window_geometry(42, [100, 200, 800, 600], "normal")
    gui.ShowWindow.assert_any_call(42, win32con.SW_RESTORE)
    gui.SetWindowPos.assert_called_once_with(42, win32con.HWND_TOP, 100, 200, 800, 600, win32con.SWP_NOZORDER)


def test_set_window_geometry_maximized():
    import restore
    import win32con
    win32con.SW_RESTORE = 9
    win32con.HWND_TOP = 0
    win32con.SWP_NOZORDER = 4
    win32con.SW_MAXIMIZE = 3
    win32con.SW_MINIMIZE = 6

    with patch("restore.win32gui") as gui:
        restore._set_window_geometry(42, [0, 0, 1920, 1080], "maximized")
    gui.ShowWindow.assert_called_with(42, win32con.SW_MAXIMIZE)


def test_restore_window_already_running():
    import restore
    with patch("restore._find_window_by_exe", return_value=99), \
         patch("restore._set_window_geometry") as geom, \
         patch("restore.Path") as mock_path:
        result = restore.restore_window(
            {"title": "App", "exe": r"C:\app.exe", "rect": [0, 0, 800, 600], "state": "normal"}
        )
    assert result is True
    geom.assert_called_once_with(99, [0, 0, 800, 600], "normal")


def test_restore_window_not_running_launches_it(tmp_path):
    import restore
    fake_exe = tmp_path / "app.exe"
    fake_exe.write_text("")

    call_count = {"n": 0}
    def fake_find(exe, timeout=0.5):
        call_count["n"] += 1
        return None if call_count["n"] == 1 else 88

    with patch("restore._find_window_by_exe", side_effect=fake_find), \
         patch("restore.subprocess.Popen") as popen, \
         patch("restore._set_window_geometry"):
        result = restore.restore_window(
            {"title": "App", "exe": str(fake_exe), "rect": [0, 0, 800, 600], "state": "normal"}
        )
    assert result is True
    popen.assert_called_once()


def test_restore_window_exe_missing():
    import restore
    with patch("restore._find_window_by_exe", return_value=None), \
         patch("restore.Path") as mock_path:
        mock_path.return_value.exists.return_value = False
        result = restore.restore_window(
            {"title": "Gone", "exe": r"C:\missing.exe", "rect": [0, 0, 100, 100], "state": "normal"}
        )
    assert result is False


def test_restore_profile_summary():
    import restore
    profile = {
        "windows": [
            {"title": "App1", "exe": r"C:\a.exe", "rect": [0,0,100,100], "state": "normal"},
            {"title": "App2", "exe": r"C:\b.exe", "rect": [0,0,100,100], "state": "normal"},
        ],
        "browsers": [
            {"app": "chrome", "exe": r"C:\chrome.exe", "rect": [0,0,1920,1080],
             "state": "normal", "tabs": ["https://a.com"]},
        ],
    }
    with patch("restore.restore_window", side_effect=[True, False]), \
         patch("restore.restore_browser", return_value=True):
        summary = restore.restore_profile(profile)
    assert len(summary["succeeded"]) == 2  # App1 + chrome
    assert len(summary["failed"]) == 1     # App2
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_restore.py -v
```

Expected: `ModuleNotFoundError: No module named 'restore'`

- [ ] **Step 3: Create `restore.py`**

```python
import subprocess
import time
import win32gui
import win32con
import win32process
import psutil
from pathlib import Path
from typing import Optional


def _find_window_by_exe(exe_path: str, timeout: float = 5.0) -> Optional[int]:
    """Poll for a visible window owned by the given exe. Returns hwnd or None."""
    exe_name = Path(exe_path).name.lower()
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if not win32gui.GetWindowText(hwnd):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if Path(psutil.Process(pid).exe()).name.lower() == exe_name:
                    found.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.3)
    return None


def _set_window_geometry(hwnd: int, rect: list, state: str):
    """Apply [left, top, width, height] and state to window hwnd."""
    left, top, w, h = rect
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, left, top, w, h, win32con.SWP_NOZORDER)
    if state == "maximized":
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    elif state == "minimized":
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)


def restore_window(window: dict) -> bool:
    """Ensure app is running and reposition its window. Returns True on success."""
    exe = window["exe"]
    hwnd = _find_window_by_exe(exe, timeout=0.5)
    if hwnd is None:
        if not Path(exe).exists():
            return False
        subprocess.Popen([exe])
        hwnd = _find_window_by_exe(exe, timeout=5.0)
        if hwnd is None:
            return False
    for _ in range(3):
        try:
            _set_window_geometry(hwnd, window["rect"], window["state"])
            return True
        except Exception:
            time.sleep(0.5)
    return False


def restore_browser(browser: dict) -> bool:
    """Open browser with saved tabs and reposition its window. Returns True on success."""
    exe = browser["exe"]
    app = browser["app"]
    tabs = browser.get("tabs", [])
    port = 9222 if app == "chrome" else 9223
    try:
        subprocess.Popen([exe, f"--remote-debugging-port={port}"] + tabs)
        hwnd = _find_window_by_exe(exe, timeout=6.0)
        if hwnd is None:
            return False
        _set_window_geometry(hwnd, browser["rect"], browser.get("state", "normal"))
        return True
    except Exception:
        return False


def restore_profile(profile: dict) -> dict:
    """Restore all windows and browsers. Returns {'succeeded': [...], 'failed': [...]}."""
    results: dict = {"succeeded": [], "failed": []}
    for window in profile.get("windows", []):
        ok = restore_window(window)
        label = window.get("title") or window.get("exe")
        (results["succeeded"] if ok else results["failed"]).append(label)
    for b in profile.get("browsers", []):
        ok = restore_browser(b)
        label = f"{b['app']} ({len(b.get('tabs', []))} tabs)"
        (results["succeeded"] if ok else results["failed"]).append(label)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_restore.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add restore.py tests/test_restore.py
git commit -m "feat: restore.py — launch apps, reposition windows, open browser tabs"
```

---

## Task 6: `hotkeys.py` — Global Hotkey Registration

**Files:**
- Create: `hotkeys.py`
- Create: `tests/test_hotkeys.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hotkeys.py`:

```python
from unittest.mock import patch, MagicMock, call
import pytest


@pytest.fixture(autouse=True)
def reset_hotkeys():
    import hotkeys
    hotkeys._registered.clear()
    hotkeys._callbacks.clear()
    yield
    hotkeys._registered.clear()
    hotkeys._callbacks.clear()


def test_register_hotkey():
    import hotkeys
    cb = MagicMock()
    with patch("hotkeys.keyboard") as kb:
        result = hotkeys.register("save", "ctrl+alt+s", cb)
    assert result is True
    assert hotkeys._registered["save"] == "ctrl+alt+s"
    kb.add_hotkey.assert_called_once_with("ctrl+alt+s", cb, suppress=False)


def test_register_conflict_returns_false():
    import hotkeys
    cb1, cb2 = MagicMock(), MagicMock()
    with patch("hotkeys.keyboard"):
        hotkeys.register("save", "ctrl+alt+s", cb1)
        result = hotkeys.register("restore_last", "ctrl+alt+s", cb2)
    assert result is False
    assert "restore_last" not in hotkeys._registered


def test_reregister_same_action_replaces():
    import hotkeys
    cb1, cb2 = MagicMock(), MagicMock()
    with patch("hotkeys.keyboard") as kb:
        hotkeys.register("save", "ctrl+alt+s", cb1)
        result = hotkeys.register("save", "ctrl+alt+x", cb2)
    assert result is True
    assert hotkeys._registered["save"] == "ctrl+alt+x"
    kb.remove_hotkey.assert_called_once()


def test_unregister_removes_hotkey():
    import hotkeys
    cb = MagicMock()
    with patch("hotkeys.keyboard") as kb:
        hotkeys.register("save", "ctrl+alt+s", cb)
        hotkeys.unregister("save")
    assert "save" not in hotkeys._registered
    kb.remove_hotkey.assert_called()


def test_unregister_all():
    import hotkeys
    with patch("hotkeys.keyboard"):
        hotkeys.register("save", "ctrl+alt+s", MagicMock())
        hotkeys.register("restore_last", "ctrl+alt+r", MagicMock())
        hotkeys.unregister_all()
    assert hotkeys._registered == {}


def test_apply_config_registers_all_actions():
    import hotkeys
    callbacks = {
        "save": MagicMock(),
        "restore_last": MagicMock(),
        "open_settings": MagicMock(),
    }
    config = {
        "save": "ctrl+alt+s",
        "restore_last": "ctrl+alt+r",
        "open_settings": "ctrl+alt+w",
        "quick_restore": {},
    }
    with patch("hotkeys.keyboard"):
        hotkeys.apply_config(config, callbacks)
    assert hotkeys._registered["save"] == "ctrl+alt+s"
    assert hotkeys._registered["restore_last"] == "ctrl+alt+r"
    assert hotkeys._registered["open_settings"] == "ctrl+alt+w"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_hotkeys.py -v
```

Expected: `ModuleNotFoundError: No module named 'hotkeys'`

- [ ] **Step 3: Create `hotkeys.py`**

```python
import keyboard
from typing import Callable, Optional

_registered: dict = {}   # action -> combo
_callbacks: dict = {}    # action -> callable


def register(action: str, combo: str, callback: Callable) -> bool:
    """Register a global hotkey for action. Returns False if combo conflicts with another action."""
    for existing_action, existing_combo in _registered.items():
        if existing_combo == combo and existing_action != action:
            return False
    if action in _registered:
        try:
            keyboard.remove_hotkey(_registered[action])
        except Exception:
            pass
    keyboard.add_hotkey(combo, callback, suppress=False)
    _registered[action] = combo
    _callbacks[action] = callback
    return True


def unregister(action: str):
    if action in _registered:
        try:
            keyboard.remove_hotkey(_registered[action])
        except Exception:
            pass
        del _registered[action]
        _callbacks.pop(action, None)


def unregister_all():
    for action in list(_registered.keys()):
        unregister(action)


def get_combo(action: str) -> Optional[str]:
    return _registered.get(action)


def apply_config(hotkey_config: dict, callbacks: dict):
    """Register all hotkeys from a config dict. Replaces all existing hotkeys."""
    unregister_all()
    for action, value in hotkey_config.items():
        if action == "quick_restore":
            qr_cb = callbacks.get("quick_restore")
            if qr_cb:
                for slot, profile_name in value.items():
                    register(
                        f"quick_restore_{slot}",
                        f"ctrl+alt+{slot}",
                        lambda pn=profile_name: qr_cb(pn),
                    )
        else:
            cb = callbacks.get(action)
            if cb and value:
                register(action, value, cb)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_hotkeys.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add hotkeys.py tests/test_hotkeys.py
git commit -m "feat: hotkeys.py — register/unregister global hotkeys with conflict detection"
```

---

## Task 7: `tray.py` — System Tray Icon

**Files:**
- Create: `tray.py`

No unit tests for the tray icon (pystray requires a real display). Manual smoke test in Task 9.

- [ ] **Step 1: Create `tray.py`**

```python
import threading
from pathlib import Path
from typing import Callable, Optional
import pystray
from PIL import Image, ImageDraw


def _make_icon_image() -> Image.Image:
    """Generate a simple monitor icon for the tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Monitor outline
    draw.rectangle([4, 8, 60, 46], fill=(70, 130, 180), outline=(200, 230, 255), width=2)
    # Screen area
    draw.rectangle([8, 12, 56, 42], fill=(20, 30, 50))
    # Three window lines
    draw.rectangle([12, 16, 34, 24], fill=(100, 180, 255))
    draw.rectangle([36, 16, 52, 24], fill=(100, 180, 255))
    draw.rectangle([12, 28, 52, 38], fill=(80, 160, 220))
    # Stand
    draw.rectangle([28, 47, 36, 54], fill=(70, 130, 180))
    draw.rectangle([20, 54, 44, 58], fill=(70, 130, 180))
    return img


def _load_icon(icon_path: Optional[str]) -> Image.Image:
    if icon_path:
        try:
            return Image.open(icon_path)
        except Exception:
            pass
    assets_icon = Path(__file__).parent / "assets" / "icon.png"
    if assets_icon.exists():
        try:
            return Image.open(assets_icon)
        except Exception:
            pass
    return _make_icon_image()


def _build_menu(
    on_save: Callable,
    on_restore: Callable,
    profile_names: list,
    on_open_settings: Callable,
    on_exit: Callable,
) -> pystray.Menu:
    restore_items = [
        pystray.MenuItem(name, lambda _, n=name: on_restore(n))
        for name in profile_names
    ]
    if not restore_items:
        restore_items = [pystray.MenuItem("(no profiles saved)", None, enabled=False)]
    return pystray.Menu(
        pystray.MenuItem("Save Current Layout", on_save),
        pystray.MenuItem("Restore", pystray.Menu(*restore_items)),
        pystray.MenuItem("Open Settings", on_open_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )


class TrayApp:
    def __init__(self):
        self._image = _load_icon(None)
        self._icon: Optional[pystray.Icon] = None
        self._on_save: Optional[Callable] = None
        self._on_restore: Optional[Callable] = None
        self._on_open_settings: Optional[Callable] = None
        self._on_exit: Optional[Callable] = None
        self._get_profiles: Optional[Callable] = None

    def setup(
        self,
        on_save: Callable,
        on_restore: Callable,
        on_open_settings: Callable,
        on_exit: Callable,
        get_profiles: Callable,
    ):
        self._on_save = on_save
        self._on_restore = on_restore
        self._on_open_settings = on_open_settings
        self._on_exit = on_exit
        self._get_profiles = get_profiles

    def run_detached(self):
        """Start the tray icon in a daemon thread. Non-blocking."""
        menu = _build_menu(
            self._on_save,
            self._on_restore,
            self._get_profiles(),
            self._on_open_settings,
            self._on_exit,
        )
        self._icon = pystray.Icon("ScreenSetupSaver", self._image, "Screen Setup Saver", menu)
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()

    def update_menu(self):
        """Rebuild and apply the tray menu (call after profile list changes)."""
        if self._icon:
            self._icon.menu = _build_menu(
                self._on_save,
                self._on_restore,
                self._get_profiles(),
                self._on_open_settings,
                self._on_exit,
            )
            self._icon.update_menu()

    def stop(self):
        if self._icon:
            self._icon.stop()
```

- [ ] **Step 2: Commit**

```
git add tray.py
git commit -m "feat: tray.py — system tray icon with dynamic right-click menu"
```

---

## Task 8: `settings_ui.py` — Settings Window

**Files:**
- Create: `settings_ui.py`

No automated tests (tkinter GUI). Manual smoke test in Task 9.

- [ ] **Step 1: Create `settings_ui.py`**

```python
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from datetime import datetime
from typing import Callable
import browser
import hotkeys as hotkeys_mod


class SettingsWindow:
    def __init__(
        self,
        root: tk.Tk,
        get_profiles: Callable,
        save_current_cb: Callable,
        restore_cb: Callable,
        delete_cb: Callable,
        rename_cb: Callable,
        get_config: Callable,
        save_config_cb: Callable,
        reload_hotkeys_cb: Callable,
        on_after_change: Callable,
    ):
        self._root = root
        self._win: tk.Toplevel = None
        self._get_profiles = get_profiles
        self._save_current_cb = save_current_cb
        self._restore_cb = restore_cb
        self._delete_cb = delete_cb
        self._rename_cb = rename_cb
        self._get_config = get_config
        self._save_config_cb = save_config_cb
        self._reload_hotkeys_cb = reload_hotkeys_cb
        self._on_after_change = on_after_change
        self._hotkey_vars: dict = {}
        self._recording: dict = {}  # action -> tk.Entry currently recording

    def show(self):
        self._root.after(0, self._show_on_main_thread)

    def _show_on_main_thread(self):
        if self._win and self._win.winfo_exists():
            self._win.lift()
            self._win.focus_force()
            return
        self._build()

    def _build(self):
        self._win = tk.Toplevel(self._root)
        self._win.title("Screen Setup Saver")
        self._win.geometry("640x460")
        self._win.resizable(False, False)

        notebook = ttk.Notebook(self._win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_profiles_tab(notebook)
        self._build_hotkeys_tab(notebook)
        self._build_browser_tab(notebook)

    # ── Profiles Tab ──────────────────────────────────────────────────────────

    def _build_profiles_tab(self, notebook: ttk.Notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Profiles")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=6, pady=(6, 2))
        ttk.Button(btn_frame, text="💾 Save Current", command=self._do_save).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔁 Restore Selected", command=self._do_restore).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="✏ Rename", command=self._do_rename).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑 Delete", command=self._do_delete).pack(side=tk.LEFT, padx=2)

        cols = ("name", "saved", "windows", "tabs")
        self._tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        self._tree.heading("name", text="Name")
        self._tree.heading("saved", text="Saved")
        self._tree.heading("windows", text="Windows")
        self._tree.heading("tabs", text="Tabs")
        self._tree.column("name", width=200)
        self._tree.column("saved", width=140)
        self._tree.column("windows", width=70, anchor=tk.CENTER)
        self._tree.column("tabs", width=60, anchor=tk.CENTER)
        self._tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._tree.bind("<<TreeviewSelect>>", self._on_profile_select)

        self._preview = tk.Text(frame, height=5, state=tk.DISABLED, wrap=tk.WORD)
        self._preview.pack(fill=tk.X, padx=6, pady=(0, 6))

        self._refresh_profiles()

    def _refresh_profiles(self):
        self._tree.delete(*self._tree.get_children())
        for p in self._get_profiles():
            saved_dt = p.get("saved_at", "")
            try:
                saved_dt = datetime.fromisoformat(saved_dt).strftime("%b %d %H:%M")
            except Exception:
                pass
            n_windows = len(p.get("windows", []))
            n_tabs = sum(len(b.get("tabs", [])) for b in p.get("browsers", []))
            self._tree.insert("", tk.END, iid=p["name"],
                              values=(p["name"], saved_dt, n_windows, n_tabs))

    def _selected_profile_name(self):
        sel = self._tree.selection()
        return sel[0] if sel else None

    def _on_profile_select(self, _event=None):
        name = self._selected_profile_name()
        if not name:
            return
        profiles = {p["name"]: p for p in self._get_profiles()}
        p = profiles.get(name)
        if not p:
            return
        lines = []
        for w in p.get("windows", []):
            lines.append(f"🪟  {w['title']}")
        for b in p.get("browsers", []):
            tab_str = ", ".join(b.get("tabs", [])[:3])
            if len(b.get("tabs", [])) > 3:
                tab_str += f" +{len(b['tabs']) - 3} more"
            lines.append(f"🌐  {b['app'].title()} — {tab_str}")
        self._preview.config(state=tk.NORMAL)
        self._preview.delete("1.0", tk.END)
        self._preview.insert(tk.END, "\n".join(lines) or "(empty profile)")
        self._preview.config(state=tk.DISABLED)

    def _do_save(self):
        name = simpledialog.askstring("Save Layout", "Profile name:", parent=self._win)
        if name:
            self._save_current_cb(name)
            self._refresh_profiles()
            self._on_after_change()

    def _do_restore(self):
        name = self._selected_profile_name()
        if not name:
            messagebox.showinfo("Restore", "Select a profile first.", parent=self._win)
            return
        self._win.withdraw()
        result = self._restore_cb(name)
        self._win.deiconify()
        failed = result.get("failed", [])
        if failed:
            messagebox.showwarning("Restore",
                f"Restored with issues:\nFailed: {', '.join(failed)}", parent=self._win)

    def _do_rename(self):
        name = self._selected_profile_name()
        if not name:
            return
        new_name = simpledialog.askstring("Rename", "New name:", initialvalue=name, parent=self._win)
        if new_name and new_name != name:
            ok = self._rename_cb(name, new_name)
            if ok:
                self._refresh_profiles()
                self._on_after_change()
            else:
                messagebox.showerror("Rename", "Name already in use.", parent=self._win)

    def _do_delete(self):
        name = self._selected_profile_name()
        if not name:
            return
        if messagebox.askyesno("Delete", f"Delete '{name}'?", parent=self._win):
            self._delete_cb(name)
            self._refresh_profiles()
            self._on_after_change()

    # ── Hotkeys Tab ───────────────────────────────────────────────────────────

    def _build_hotkeys_tab(self, notebook: ttk.Notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Hotkeys")

        actions = [
            ("save", "Save Current Layout"),
            ("restore_last", "Restore Last Profile"),
            ("open_settings", "Open Settings Window"),
        ]
        config = self._get_config()
        self._hotkey_vars = {}

        for row, (action, label) in enumerate(actions):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
            var = tk.StringVar(value=config["hotkeys"].get(action, ""))
            self._hotkey_vars[action] = var
            entry = ttk.Entry(frame, textvariable=var, width=20)
            entry.grid(row=row, column=1, padx=10)
            entry.bind("<FocusIn>", lambda e, a=action, en=entry: self._start_recording(a, en))
            entry.bind("<FocusOut>", lambda e, a=action: self._stop_recording(a))
            entry.bind("<KeyPress>", lambda e, a=action: self._record_key(e, a))

        self._hotkey_status = ttk.Label(frame, text="", foreground="red")
        self._hotkey_status.grid(row=len(actions), column=0, columnspan=2, padx=10, pady=4)

        ttk.Button(frame, text="Apply Hotkeys", command=self._apply_hotkeys).grid(
            row=len(actions) + 1, column=0, columnspan=2, pady=8
        )

    def _start_recording(self, action: str, entry: ttk.Entry):
        self._recording[action] = entry
        self._hotkey_vars[action].set("")
        self._hotkey_status.config(text=f"Press keys for '{action}'... (Esc to cancel)")

    def _stop_recording(self, action: str):
        self._recording.pop(action, None)

    def _record_key(self, event, action: str):
        if action not in self._recording:
            return
        parts = []
        if event.state & 0x4:
            parts.append("ctrl")
        if event.state & 0x1:
            parts.append("shift")
        if event.state & 0x20000:
            parts.append("alt")
        key = event.keysym.lower()
        if key == "escape":
            self._hotkey_vars[action].set(hotkeys_mod.get_combo(action) or "")
            self._stop_recording(action)
            self._hotkey_status.config(text="Cancelled.")
            return "break"
        if key not in ("control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r"):
            parts.append(key)
            combo = "+".join(parts)
            self._hotkey_vars[action].set(combo)
            self._hotkey_status.config(text=f"Set to: {combo}")
            self._stop_recording(action)
        return "break"

    def _apply_hotkeys(self):
        config = self._get_config()
        for action, var in self._hotkey_vars.items():
            config["hotkeys"][action] = var.get()
        self._save_config_cb(config)
        self._reload_hotkeys_cb()
        self._hotkey_status.config(text="Hotkeys applied.", foreground="green")

    # ── Browser Setup Tab ─────────────────────────────────────────────────────

    def _build_browser_tab(self, notebook: ttk.Notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Browser Setup")

        ttk.Label(frame, text="CDP Debug Port Status", font=("", 10, "bold")).pack(
            anchor=tk.W, padx=12, pady=(12, 4)
        )

        self._chrome_status = ttk.Label(frame, text="")
        self._chrome_status.pack(anchor=tk.W, padx=20, pady=2)
        self._edge_status = ttk.Label(frame, text="")
        self._edge_status.pack(anchor=tk.W, padx=20, pady=2)

        ttk.Button(frame, text="🔄 Refresh Status", command=self._refresh_browser_status).pack(
            anchor=tk.W, padx=12, pady=6
        )

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=8)

        ttk.Label(frame, text="Create Debug Shortcuts", font=("", 10, "bold")).pack(
            anchor=tk.W, padx=12
        )
        ttk.Label(
            frame,
            text=(
                "Creates Desktop + Start Menu shortcuts for Chrome and Edge\n"
                "with --remote-debugging-port flags. Your existing shortcuts\n"
                "are backed up before being replaced."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=20, pady=4)

        ttk.Button(frame, text="Create Debug Shortcuts", command=self._create_shortcuts).pack(
            anchor=tk.W, padx=12, pady=4
        )

        self._shortcut_status = ttk.Label(frame, text="")
        self._shortcut_status.pack(anchor=tk.W, padx=20)

        self._refresh_browser_status()

    def _refresh_browser_status(self):
        for name, label in [("chrome", self._chrome_status), ("edge", self._edge_status)]:
            connected = browser.is_connected(name)
            if connected:
                label.config(text=f"✅  {name.title()} — connected (port {9222 if name=='chrome' else 9223})",
                              foreground="green")
            else:
                label.config(text=f"❌  {name.title()} — not connected (launch via debug shortcut)",
                              foreground="red")

    def _create_shortcuts(self):
        try:
            _create_browser_debug_shortcuts()
            self._shortcut_status.config(
                text="✅ Shortcuts created on Desktop and Start Menu.", foreground="green"
            )
        except Exception as e:
            self._shortcut_status.config(text=f"❌ Error: {e}", foreground="red")


# ── Shortcut creation helper ───────────────────────────────────────────────────

def _create_browser_debug_shortcuts():
    """Create .lnk shortcuts for Chrome and Edge with debug port flags."""
    import winreg
    import os
    import shutil
    from pathlib import Path

    try:
        import win32com.client
    except ImportError:
        raise RuntimeError("pywin32 required for shortcut creation")

    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    browser_paths = {
        "chrome": _find_browser_exe("chrome"),
        "edge": _find_browser_exe("edge"),
    }
    debug_flags = {
        "chrome": "--remote-debugging-port=9222",
        "edge": "--remote-debugging-port=9223",
    }
    shortcut_names = {
        "chrome": "Google Chrome (Debug).lnk",
        "edge": "Microsoft Edge (Debug).lnk",
    }

    shell = win32com.client.Dispatch("WScript.Shell")
    for name, exe in browser_paths.items():
        if not exe:
            continue
        for folder in [desktop, start_menu]:
            lnk_path = str(folder / shortcut_names[name])
            shortcut = shell.CreateShortCut(lnk_path)
            shortcut.Targetpath = exe
            shortcut.Arguments = debug_flags[name]
            shortcut.WorkingDirectory = str(Path(exe).parent)
            shortcut.save()


def _find_browser_exe(browser_name: str) -> str:
    """Return path to Chrome or Edge executable from known install locations."""
    import os
    candidates = {
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
    for path in candidates.get(browser_name, []):
        if os.path.exists(path):
            return path
    return ""
```

- [ ] **Step 2: Commit**

```
git add settings_ui.py
git commit -m "feat: settings_ui.py — tkinter settings window with Profiles, Hotkeys, Browser Setup tabs"
```

---

## Task 9: `main.py` — Wire Everything Together

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
import sys
import threading
import tkinter as tk
import tkinter.messagebox as msgbox
from datetime import datetime
from pathlib import Path

import profiles
import capture
import browser
import restore as restore_mod
import hotkeys as hotkeys_mod
import tray as tray_mod
from settings_ui import SettingsWindow


def _build_profile(name: str) -> dict:
    """Capture current screen state and return a profile dict."""
    windows = capture.capture_windows()
    regular, browser_wins = capture.split_windows(windows)

    browsers = []
    for bname in ("chrome", "edge"):
        tabs = browser.get_tabs(bname)
        # Find the browser window(s) captured by win32gui
        matching = [w for w in browser_wins if Path(w["exe"]).name.lower() == browser.BROWSER_EXES[bname]]
        rect = matching[0]["rect"] if matching else [0, 0, 1920, 1080]
        state = matching[0]["state"] if matching else "normal"
        exe = matching[0]["exe"] if matching else ""
        if tabs or matching:
            browsers.append({
                "app": bname,
                "exe": exe,
                "rect": rect,
                "state": state,
                "tabs": tabs,
            })

    return {
        "name": name,
        "saved_at": datetime.now().isoformat(),
        "windows": regular,
        "browsers": browsers,
    }


def main():
    # ── Setup ──────────────────────────────────────────────────────────────────
    profiles.ensure_dirs()
    config = profiles.load_config()

    root = tk.Tk()
    root.withdraw()
    root.title("Screen Setup Saver")

    tray = tray_mod.TrayApp()
    settings_win: SettingsWindow = None

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def get_profile_names() -> list:
        return [p["name"] for p in profiles.list_profiles()]

    def do_save_named(name: str):
        profile = _build_profile(name)
        profiles.save_profile(profile)
        config["last_profile"] = name
        profiles.save_config(config)
        tray.update_menu()
        profiles.log(f"Saved profile: {name}")

    def do_save_hotkey():
        last = config.get("last_profile")
        if last:
            do_save_named(last)
        else:
            # No last profile — prompt via a simple dialog on the main thread
            root.after(0, _prompt_and_save)

    def _prompt_and_save():
        name = tk.simpledialog.askstring("Save Layout", "Profile name:", parent=root)
        if name:
            do_save_named(name)

    def do_restore(name: str) -> dict:
        profile = profiles.load_profile(name)
        if profile is None:
            return {"succeeded": [], "failed": [f"Profile '{name}' not found"]}
        result = restore_mod.restore_profile(profile)
        config["last_profile"] = name
        profiles.save_config(config)
        profiles.log(f"Restored profile: {name}, failed: {result['failed']}")
        return result

    def do_restore_last():
        last = config.get("last_profile")
        if last:
            do_restore(last)

    def do_open_settings():
        if settings_win:
            settings_win.show()

    def do_exit():
        hotkeys_mod.unregister_all()
        tray.stop()
        root.quit()

    def reload_hotkeys():
        fresh = profiles.load_config()
        config.update(fresh)
        hotkeys_mod.apply_config(
            config["hotkeys"],
            {
                "save": do_save_hotkey,
                "restore_last": do_restore_last,
                "open_settings": do_open_settings,
                "quick_restore": do_restore,
            },
        )

    # ── Settings window ────────────────────────────────────────────────────────

    settings_win = SettingsWindow(
        root=root,
        get_profiles=profiles.list_profiles,
        save_current_cb=do_save_named,
        restore_cb=do_restore,
        delete_cb=profiles.delete_profile,
        rename_cb=profiles.rename_profile,
        get_config=profiles.load_config,
        save_config_cb=profiles.save_config,
        reload_hotkeys_cb=reload_hotkeys,
        on_after_change=tray.update_menu,
    )

    # ── Tray ──────────────────────────────────────────────────────────────────

    tray.setup(
        on_save=lambda: root.after(0, _prompt_and_save),
        on_restore=lambda name: threading.Thread(target=do_restore, args=(name,), daemon=True).start(),
        on_open_settings=do_open_settings,
        on_exit=do_exit,
        get_profiles=get_profile_names,
    )

    # ── Hotkeys ──────────────────────────────────────────────────────────────

    reload_hotkeys()

    # ── Start ─────────────────────────────────────────────────────────────────

    tray.run_detached()
    profiles.log("App started")
    root.mainloop()


if __name__ == "__main__":
    # The keyboard library needs admin on some setups; warn gracefully
    try:
        main()
    except Exception as e:
        import traceback
        try:
            import tkinter.messagebox as mb
            mb.showerror("Screen Setup Saver", f"Fatal error:\n{e}\n\n{traceback.format_exc()}")
        except Exception:
            print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 2: Run full test suite to ensure nothing broke**

```
pytest tests/ -v
```

Expected: all tests PASS (20+ tests).

- [ ] **Step 3: Smoke test — launch the app**

```
python main.py
```

Expected:
- A tray icon appears in the Windows taskbar system tray
- Right-clicking shows: Save Current Layout, Restore (submenu), Open Settings, Exit
- `Ctrl+Alt+W` opens the Settings window
- Profiles tab is empty initially
- Hotkeys tab shows the three default shortcuts
- Browser Setup tab shows Chrome/Edge connection status

- [ ] **Step 4: Commit**

```
git add main.py
git commit -m "feat: main.py — wire all modules, start tray + tkinter event loop"
```

---

## Task 10: Distribution Files

**Files:**
- Create: `run.bat` (already done in Task 1 — verify it works)
- Create: `README.md`

- [ ] **Step 1: Verify `run.bat` launches the app**

Double-click `run.bat`. Expected: app starts with tray icon.

- [ ] **Step 2: Create `README.md`**

```markdown
# Screen Setup Saver

Save and restore your Windows screen layout — window positions, running apps, and browser tabs.

## Requirements

- Windows 11
- Python 3.11+

## Install

```
pip install -r requirements.txt
```

## Run

```
python main.py
```

Or double-click `run.bat`.

## First-time Setup (Browser Tab Capture)

1. Open **Settings → Browser Setup**
2. Click **Create Debug Shortcuts**
3. From now on, launch Chrome/Edge via the new "Debug" shortcuts on your Desktop

## Default Hotkeys

| Action | Shortcut |
|---|---|
| Save current layout | `Ctrl+Alt+S` |
| Restore last profile | `Ctrl+Alt+R` |
| Open settings | `Ctrl+Alt+W` |

Hotkeys are configurable in Settings → Hotkeys.

## Auto-start with Windows

Drop a shortcut to `run.bat` in:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```
```

- [ ] **Step 3: Final test run**

```
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Final commit**

```
git add README.md
git commit -m "docs: add README with setup and usage instructions"
```

---

## Self-Review Checklist

- ✅ **profiles.py** — load/save/list/delete/rename + config with defaults
- ✅ **capture.py** — EnumWindows, filter, rect as [left, top, width, height], state, split_windows
- ✅ **browser.py** — CDP HTTP endpoint, both browsers, empty on failure
- ✅ **restore.py** — launch + poll + reposition + browser restore + summary
- ✅ **hotkeys.py** — register/unregister/conflict/apply_config
- ✅ **tray.py** — dynamic menu, run_detached, update_menu
- ✅ **settings_ui.py** — 3 tabs, hotkey recording, shortcut creation, browser status
- ✅ **main.py** — wires all callbacks, hidden tkinter root, daemon tray thread
- ✅ **Error handling** — all error table scenarios covered (missing exe, corrupt profile, no debug port)
- ✅ **Logging** — `profiles.log()` used in main.py for key events
- ✅ **README** — setup, browser shortcut instructions, hotkey table
