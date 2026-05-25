# Browser Capture + Profiles UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make browser URL capture understandable and user-friendly, fix cross-browser URL restore routing, and redesign profile details to a side-by-side layout that clearly shows what was saved.

**Architecture:** Introduce focused browser-runtime helpers for launch/status checks, centralize profile payload creation so save paths stay consistent, and harden restore routing with browser-specific executable resolution that prefers saved hints. Rework the Profiles tab with a left list/actions pane and right details pane, then add Browser Setup actions that remove manual PowerShell steps.

**Tech Stack:** Python 3.13, tkinter/ttk, pystray, win32 APIs, pytest/unittest.mock, NSIS build pipeline.

---

## Scope Check

This spec has three related concerns (capture UX, profile details UX, restore routing) that all touch the same user flow (save → inspect profile → restore). Keep this as one plan so behavior stays coherent and testable end-to-end.

## File Structure and Responsibilities

- Create: `browser_runtime.py`  
  Owns browser executable discovery, debug-mode launch commands, and capture-status probing helpers.

- Create: `profile_builder.py`  
  Builds the saved profile payload in one place (`windows`, `browser_tabs`, and `browser_exes` hints) so `main.py` and `settings_ui.py` stay DRY.

- Modify: `settings_ui.py`  
  1) Side-by-side Profiles layout (left list/actions, right details), 2) Browser Setup launch/test controls, 3) save-time warning when no browser tabs are captured.

- Modify: `main.py`  
  Use `profile_builder.build_profile_payload()` for tray/hotkey save flow.

- Modify: `restore.py`  
  Add browser executable resolution priority using saved `browser_exes` hints, installed paths, and running-process preference before default-browser fallback.

- Modify: `README.md`  
  Document in-app capture mode flow and expected behavior clearly.

- Create: `tests/test_browser_runtime.py`  
  Unit tests for runtime discovery, launch, and probe/status behavior.

- Create: `tests/test_profile_builder.py`  
  Unit tests for save payload shape and `browser_exes` persistence.

- Modify: `tests/test_restore.py`  
  Add routing tests for browser-specific restore and fallback warnings.

- Modify: `tests/test_settings_ui.py`  
  Add tests for profile detail messaging and Browser Setup actions.

---

### Task 1: Add browser runtime helper module

**Files:**
- Create: `browser_runtime.py`
- Test: `tests/test_browser_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_runtime.py
from unittest.mock import Mock, patch


class TestFindBrowserExe:
    def test_returns_first_existing_candidate(self):
        import browser_runtime
        with patch("browser_runtime.os.path.isfile", side_effect=lambda p: "msedge.exe" in p.lower()):
            exe = browser_runtime.find_browser_exe("edge")
        assert exe is not None
        assert exe.lower().endswith("msedge.exe")


class TestLaunchBrowserCaptureMode:
    def test_launches_with_debug_flags(self):
        import browser_runtime
        with patch("browser_runtime.find_browser_exe", return_value=r"C:\Edge\msedge.exe"), \
             patch("browser_runtime.subprocess.Popen") as mock_popen:
            browser_runtime.launch_browser_capture_mode("edge", 9223, "127.0.0.1")

        mock_popen.assert_called_once_with([
            r"C:\Edge\msedge.exe",
            "--remote-debugging-port=9223",
            "--remote-debugging-address=127.0.0.1",
        ])


class TestProbeCaptureStatus:
    def test_probe_success_sets_connected_true(self):
        import browser_runtime
        with patch("browser_runtime._probe_port", side_effect=[True, False]), \
             patch("browser_runtime.browser.capture_browser_tabs", return_value={"chrome": ["https://a"], "edge": []}):
            status = browser_runtime.get_capture_status(9222, 9223)

        assert status["chrome"]["connected"] is True
        assert status["chrome"]["count"] == 1
        assert status["edge"]["connected"] is False
        assert status["edge"]["count"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_browser_runtime.py -v`  
Expected: `FAILED` with `ModuleNotFoundError: No module named 'browser_runtime'`

- [ ] **Step 3: Write minimal implementation**

```python
# browser_runtime.py
from __future__ import annotations

import os
import subprocess
import urllib.request
from typing import Any

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
    for path in _BROWSER_EXES.get(browser_name, []):
        if os.path.isfile(path):
            return path
    return None


def launch_browser_capture_mode(browser_name: str, port: int, address: str = "127.0.0.1") -> subprocess.Popen[Any]:
    exe = find_browser_exe(browser_name)
    if not exe:
        raise FileNotFoundError(f"{browser_name} executable not found")
    return subprocess.Popen([
        exe,
        f"--remote-debugging-port={port}",
        f"--remote-debugging-address={address}",
    ])


def _probe_port(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except Exception:
        return False


def get_capture_status(chrome_port: int, edge_port: int) -> dict[str, dict[str, Any]]:
    tabs = browser.capture_browser_tabs(chrome_port=chrome_port, edge_port=edge_port)
    return {
        "chrome": {"connected": _probe_port(chrome_port), "count": len(tabs.get("chrome", []))},
        "edge": {"connected": _probe_port(edge_port), "count": len(tabs.get("edge", []))},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_browser_runtime.py -v`  
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add browser_runtime.py tests/test_browser_runtime.py
git commit -m "feat: add browser runtime helpers for capture mode"
```

---

### Task 2: Centralize profile payload creation and persist browser exe hints

**Files:**
- Create: `profile_builder.py`
- Modify: `main.py`
- Modify: `settings_ui.py`
- Test: `tests/test_profile_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_profile_builder.py
from unittest.mock import patch


def test_build_payload_includes_browser_exes():
    import profile_builder

    with patch("profile_builder.capture.capture_windows", return_value=[{"title": "A"}]), \
         patch("profile_builder.browser.capture_browser_tabs", return_value={"chrome": ["https://x"], "edge": []}), \
         patch("profile_builder.browser_runtime.find_browser_exe", side_effect=[r"C:\Chrome\chrome.exe", r"C:\Edge\msedge.exe"]):
        payload = profile_builder.build_profile_payload({"chrome_debug_port": 9222, "edge_debug_port": 9223})

    assert "windows" in payload
    assert "browser_tabs" in payload
    assert payload["browser_exes"]["chrome"].lower().endswith("chrome.exe")
    assert payload["browser_exes"]["edge"].lower().endswith("msedge.exe")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_builder.py -v`  
Expected: `FAILED` with `ModuleNotFoundError: No module named 'profile_builder'`

- [ ] **Step 3: Write minimal implementation**

```python
# profile_builder.py
from __future__ import annotations

from typing import Any

import browser
import browser_runtime
import capture


def build_profile_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    chrome_port = int(cfg.get("chrome_debug_port", 9222))
    edge_port = int(cfg.get("edge_debug_port", 9223))
    payload = {
        "windows": capture.capture_windows(),
        "browser_tabs": browser.capture_browser_tabs(chrome_port=chrome_port, edge_port=edge_port),
        "browser_exes": {},
    }
    chrome_exe = browser_runtime.find_browser_exe("chrome")
    edge_exe = browser_runtime.find_browser_exe("edge")
    if chrome_exe:
        payload["browser_exes"]["chrome"] = chrome_exe
    if edge_exe:
        payload["browser_exes"]["edge"] = edge_exe
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_builder.py -v`  
Expected: `1 passed`

- [ ] **Step 5: Replace duplicated save payload logic**

```python
# main.py (_do_save)
import profile_builder

data = profile_builder.build_profile_payload(cfg)
prof.save_profile(name, data)
```

```python
# settings_ui.py (_save_layout)
import profile_builder

cfg = prof.load_config()
data = profile_builder.build_profile_payload(cfg)
prof.save_profile(name, data)
```

- [ ] **Step 6: Run affected tests**

Run: `pytest tests/test_profiles.py tests/test_settings_ui.py -v`  
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add profile_builder.py main.py settings_ui.py tests/test_profile_builder.py
git commit -m "feat: persist browser executable hints in saved profiles"
```

---

### Task 3: Fix cross-browser URL restore routing with executable hints

**Files:**
- Modify: `restore.py`
- Test: `tests/test_restore.py`

- [ ] **Step 1: Write failing restore routing tests**

```python
# tests/test_restore.py (append in browser restore test area)
from unittest.mock import patch


def test_restore_uses_browser_hint_before_default_detection():
    import restore
    with patch("restore._find_browser_exe", return_value=None), \
         patch("restore._is_restorable_exe", return_value=True), \
         patch("restore.subprocess.Popen") as mock_popen:
        restore.restore_browser_tabs(
            {"chrome": ["https://example.com"]},
            {"chrome": r"C:\Portable\Chrome\chrome.exe"},
        )
    mock_popen.assert_called_once_with([r"C:\Portable\Chrome\chrome.exe", "https://example.com"])


def test_restore_routes_chrome_and_edge_to_separate_exes():
    import restore
    hints = {"chrome": r"C:\A\chrome.exe", "edge": r"C:\B\msedge.exe"}
    with patch("restore._is_restorable_exe", return_value=True), \
         patch("restore.subprocess.Popen") as mock_popen:
        restore.restore_browser_tabs(
            {"chrome": ["https://one.com"], "edge": ["https://two.com"]},
            hints,
        )
    assert mock_popen.call_args_list[0][0][0][0].lower().endswith("chrome.exe")
    assert mock_popen.call_args_list[1][0][0][0].lower().endswith("msedge.exe")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_restore.py -k "browser_hint or separate_exes" -v`  
Expected: fails because `restore_browser_tabs()` does not accept hints and routing priority is missing.

- [ ] **Step 3: Implement browser-specific resolver and new restore signature**

```python
# restore.py (core additions)
def _resolve_browser_exe(browser_name: str, browser_exes: dict[str, str] | None = None) -> str | None:
    hints = browser_exes or {}
    hinted = hints.get(browser_name)
    if hinted and _is_restorable_exe(hinted):
        return hinted

    direct = _find_browser_exe(browser_name)
    if direct and _is_restorable_exe(direct):
        return direct

    # Prefer a candidate that is currently running
    for candidate in _BROWSER_EXES.get(browser_name, []):
        if _is_restorable_exe(candidate) and _find_windows_by_exe(candidate):
            return candidate
    return None


def restore_browser_tabs(browser_tabs: dict[str, list[str]], browser_exes: dict[str, str] | None = None) -> None:
    for browser_name, urls in browser_tabs.items():
        if not urls:
            continue
        exe = _resolve_browser_exe(browser_name, browser_exes)
        for url in urls:
            if not _is_restorable_url(url):
                log.warning("Skipping non-web URL for %s: %s", browser_name, url)
                continue
            try:
                if exe:
                    subprocess.Popen([exe, url])
                    log.info("Restoring %s URL via %s", browser_name, exe)
                else:
                    webbrowser.open(url)
                    log.warning("%s executable not found; default-browser fallback used for %s", browser_name, url)
            except Exception as exc:
                log.warning("Failed to open URL %s: %s", url, exc)
```

```python
# restore.py (restore_profile call site)
browser_exes: dict[str, str] = profile.get("browser_exes", {})
if browser_tabs:
    restore_browser_tabs(browser_tabs, browser_exes)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_restore.py -v`  
Expected: all restore tests pass including new routing tests.

- [ ] **Step 5: Commit**

```bash
git add restore.py tests/test_restore.py
git commit -m "fix: route chrome and edge URL restores to correct browser executables"
```

---

### Task 4: Redesign Profiles tab to side-by-side details and improve empty-URL messaging

**Files:**
- Modify: `settings_ui.py`
- Test: `tests/test_settings_ui.py`

- [ ] **Step 1: Write failing details-message test**

```python
# tests/test_settings_ui.py (add)
def test_profile_details_empty_tabs_message_guides_capture_mode():
    import settings_ui
    text = settings_ui._format_profile_details({
        "windows": [{"exe": r"C:\Windows\notepad.exe"}],
        "browser_tabs": {"chrome": [], "edge": []},
    })
    assert "Launch browsers in Capture Mode before saving." in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_ui.py -k capture_mode -v`  
Expected: fails because current message lacks explicit guidance.

- [ ] **Step 3: Implement side-by-side layout and message update**

```python
# settings_ui.py (_build_profiles_tab structure)
split = ttk.PanedWindow(frame, orient="horizontal")
split.pack(fill="both", expand=True)

left = ttk.Frame(split)
right = ttk.Frame(split)
split.add(left, weight=3)
split.add(right, weight=2)

# left: profile list + action buttons
# right: selected profile details text
```

```python
# settings_ui.py (_format_profile_details empty case)
if url_total == 0:
    lines.append("No browser URLs saved in this profile.")
    lines.append("Launch browsers in Capture Mode before saving.")
```

- [ ] **Step 4: Run UI tests**

Run: `pytest tests/test_settings_ui.py -v`  
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add settings_ui.py tests/test_settings_ui.py
git commit -m "feat: redesign profiles tab with side-by-side details and clearer capture guidance"
```

---

### Task 5: Add Browser Setup guided actions (launch + test status)

**Files:**
- Modify: `settings_ui.py`
- Modify: `profile_builder.py`
- Test: `tests/test_settings_ui.py`

- [ ] **Step 1: Write failing tests for Browser Setup actions**

```python
# tests/test_settings_ui.py (add)
from unittest.mock import MagicMock, patch


def test_test_browser_capture_shows_counts():
    import settings_ui
    win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
    win._win = MagicMock()
    win._chrome_port_var = MagicMock(get=lambda: "9222")
    win._edge_port_var = MagicMock(get=lambda: "9223")
    with patch("settings_ui.browser_runtime.get_capture_status", return_value={
        "chrome": {"connected": True, "count": 2},
        "edge": {"connected": False, "count": 0},
    }), patch("settings_ui.messagebox.showinfo") as mock_info:
        win._test_browser_capture()
    assert "Chrome: Connected, URLs=2" in mock_info.call_args[0][1]


def test_save_layout_warns_when_no_tabs_captured():
    import settings_ui
    win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
    win._win = MagicMock()
    win._refresh_profiles = MagicMock()
    with patch("settings_ui.simpledialog.askstring", return_value="demo"), \
         patch("settings_ui.prof.load_config", return_value={}), \
         patch("settings_ui.profile_builder.build_profile_payload", return_value={"windows": [], "browser_tabs": {"chrome": [], "edge": []}}), \
         patch("settings_ui.prof.save_profile"), \
         patch("settings_ui.messagebox.showwarning") as mock_warn:
        win._save_layout()
    assert "No browser tabs captured" in mock_warn.call_args[0][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_settings_ui.py -k "browser_capture_shows_counts or warns_when_no_tabs" -v`  
Expected: fails due to missing methods/warning behavior.

- [ ] **Step 3: Implement Browser Setup controls and save warning**

```python
# settings_ui.py imports
import browser_runtime
import profile_builder
```

```python
# settings_ui.py (Browser Setup tab buttons)
ttk.Button(frame, text="Launch Chrome in Capture Mode", command=self._launch_chrome_capture_mode).pack(...)
ttk.Button(frame, text="Launch Edge in Capture Mode", command=self._launch_edge_capture_mode).pack(...)
ttk.Button(frame, text="Test browser capture now", command=self._test_browser_capture).pack(...)
```

```python
# settings_ui.py (new methods)
def _launch_chrome_capture_mode(self) -> None:
    port = int(self._chrome_port_var.get())
    browser_runtime.launch_browser_capture_mode("chrome", port, "127.0.0.1")
    messagebox.showinfo("Capture Mode", "Chrome launched in Capture Mode.", parent=self._win)

def _launch_edge_capture_mode(self) -> None:
    port = int(self._edge_port_var.get())
    browser_runtime.launch_browser_capture_mode("edge", port, "127.0.0.1")
    messagebox.showinfo("Capture Mode", "Edge launched in Capture Mode.", parent=self._win)

def _test_browser_capture(self) -> None:
    chrome_port = int(self._chrome_port_var.get())
    edge_port = int(self._edge_port_var.get())
    status = browser_runtime.get_capture_status(chrome_port, edge_port)
    msg = (
        f"Chrome: {'Connected' if status['chrome']['connected'] else 'Not connected'}, URLs={status['chrome']['count']}\n"
        f"Edge: {'Connected' if status['edge']['connected'] else 'Not connected'}, URLs={status['edge']['count']}"
    )
    messagebox.showinfo("Browser capture status", msg, parent=self._win)
```

```python
# settings_ui.py (_save_layout)
data = profile_builder.build_profile_payload(cfg)
prof.save_profile(name, data)
tab_total = len(data.get("browser_tabs", {}).get("chrome", [])) + len(data.get("browser_tabs", {}).get("edge", []))
if tab_total == 0:
    messagebox.showwarning(
        "Saved without browser URLs",
        "No browser tabs captured. Launch browsers in Capture Mode before saving.",
        parent=self._win,
    )
else:
    messagebox.showinfo("Saved", f"Profile '{name}' saved.", parent=self._win)
```

- [ ] **Step 4: Run settings tests**

Run: `pytest tests/test_settings_ui.py -v`  
Expected: all pass including new Browser Setup tests.

- [ ] **Step 5: Commit**

```bash
git add settings_ui.py profile_builder.py tests/test_settings_ui.py
git commit -m "feat: add guided browser capture controls and status checks"
```

---

### Task 6: Update documentation and run full verification

**Files:**
- Modify: `README.md`
- Test: `tests/test_browser_runtime.py`
- Test: `tests/test_profile_builder.py`
- Test: `tests/test_restore.py`
- Test: `tests/test_settings_ui.py`

- [ ] **Step 1: Update README browser section with in-app guided flow**

```markdown
## Browser Tab Capture

To include URLs, browsers must run in Capture Mode (remote debugging).

Use **Settings → Browser Setup**:
1. Set ports (Chrome 9222, Edge 9223 by default)
2. Click **Launch Chrome in Capture Mode** / **Launch Edge in Capture Mode**
3. Click **Test browser capture now**
4. Save profile

If status shows not connected, URL capture will be empty for that browser.
```

- [ ] **Step 2: Run full automated test suite**

Run: `pytest tests/ -v`  
Expected: all tests pass.

- [ ] **Step 3: Build installer artifacts smoke check**

Run: `.\build.ps1 -Version 1.0.2`  
Expected:
- PyInstaller build succeeds.
- NSIS installer build succeeds.
- Output includes `dist\installer\ScreenSetupSaver-Setup-1.0.2.exe`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: clarify capture mode workflow and browser status checks"
```

---

## Plan Self-Review (completed)

1. **Spec coverage:**  
   - Capture UX (status + one-click launch): covered in Task 5.  
   - Side-by-side profile details pane: covered in Task 4.  
   - Cross-browser URL restore routing: covered in Task 3.  
   - `browser_exes` persistence: covered in Task 2.

2. **Placeholder scan:**  
   No `TODO/TBD` placeholders. Every code-changing step includes concrete code.

3. **Type/signature consistency:**  
   - `restore_browser_tabs(browser_tabs, browser_exes=None)` signature is used consistently.
   - `profile_builder.build_profile_payload(cfg)` used consistently in `main.py` and `settings_ui.py`.

