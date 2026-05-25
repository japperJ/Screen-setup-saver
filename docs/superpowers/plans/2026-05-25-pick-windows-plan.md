# Pick Windows on Save — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Save selected…" button alongside "Save all" so the user can pick which windows to include in a profile; browser tabs auto-filter to match selected windows.

**Architecture:** `profile_builder.build_profile_payload` gains an optional `windows_filter: set[int] | None` parameter that restricts which windows and browser tabs are saved. A new `WindowPickerDialog` class in `settings_ui.py` shows a grouped, scrollable checklist. A new `_save_selected_layout()` method wires the name prompt → picker → builder → save flow. The "Save current layout" button is replaced by two side-by-side buttons.

**Tech Stack:** Python 3.11, tkinter/ttk, pytest + unittest.mock

---

## File Map

| File | Change |
|---|---|
| `profile_builder.py` | Add `windows_filter` param + `_BROWSER_NAME_TO_EXE` constant + tab-filtering logic |
| `settings_ui.py` | Add `import capture`; replace button; add `WindowPickerDialog` class; add `_save_selected_layout` method |
| `tests/test_profile_builder.py` | Add 4 new tests for filter behaviour |
| `tests/test_settings_ui.py` | Add 6 new tests for picker dialog and selective save flow |

---

## Task 1: `profile_builder.py` — `windows_filter` parameter

**Files:**
- Modify: `profile_builder.py`
- Test: `tests/test_profile_builder.py`

- [ ] **Step 1.1: Write failing tests**

Add to `tests/test_profile_builder.py` inside a new class `TestWindowsFilter`:

```python
class TestWindowsFilter:
    def test_windows_filter_excludes_unselected(self):
        import profile_builder

        cfg = {}
        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": r"C:\Windows\notepad.exe"},
            {"hwnd": 102, "title": "Explorer", "exe": r"C:\Windows\explorer.exe"},
        ]
        with patch("profile_builder.capture.capture_windows", return_value=windows), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value={"chrome": [], "edge": []}), \
             patch("profile_builder.browser_runtime.find_browser_exe", return_value=None):
            payload = profile_builder.build_profile_payload(cfg, windows_filter={101})

        assert len(payload["windows"]) == 1
        assert payload["windows"][0]["hwnd"] == 101

    def test_windows_filter_none_includes_all(self):
        import profile_builder

        cfg = {}
        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": r"C:\Windows\notepad.exe"},
            {"hwnd": 102, "title": "Explorer", "exe": r"C:\Windows\explorer.exe"},
        ]
        with patch("profile_builder.capture.capture_windows", return_value=windows), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value={"chrome": [], "edge": []}), \
             patch("profile_builder.browser_runtime.find_browser_exe", return_value=None):
            payload = profile_builder.build_profile_payload(cfg, windows_filter=None)

        assert len(payload["windows"]) == 2

    def test_browser_tabs_excluded_when_browser_not_selected(self):
        import profile_builder

        cfg = {}
        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": r"C:\Windows\notepad.exe"},
        ]
        tabs = {
            "chrome": [{"title": "Example", "url": "https://example.com"}],
            "edge": [{"title": "GitHub", "url": "https://github.com"}],
        }
        with patch("profile_builder.capture.capture_windows", return_value=windows), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value=tabs), \
             patch("profile_builder.browser_runtime.find_browser_exe", return_value=None):
            payload = profile_builder.build_profile_payload(cfg, windows_filter={101})

        # Notepad has no browser exe — both browser tab lists should be absent/empty
        assert payload["browser_tabs"].get("chrome", []) == []
        assert payload["browser_tabs"].get("edge", []) == []

    def test_browser_tabs_included_when_browser_selected(self):
        import profile_builder

        cfg = {}
        windows = [
            {"hwnd": 101, "title": "Bing - Edge", "exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"},
        ]
        tabs = {
            "chrome": [{"title": "Example", "url": "https://example.com"}],
            "edge": [{"title": "Bing", "url": "https://bing.com"}],
        }
        with patch("profile_builder.capture.capture_windows", return_value=windows), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value=tabs), \
             patch("profile_builder.browser_runtime.find_browser_exe", return_value=None), \
             patch("profile_builder.browser.match_tab_url_by_title", return_value=None):
            payload = profile_builder.build_profile_payload(cfg, windows_filter={101})

        # msedge.exe selected → edge tabs included; chrome.exe not selected → chrome absent/empty
        assert payload["browser_tabs"].get("edge") == ["https://bing.com"]
        assert payload["browser_tabs"].get("chrome", []) == []
```

- [ ] **Step 1.2: Run tests to verify they fail**

```
pytest tests/test_profile_builder.py::TestWindowsFilter -v
```

Expected: 4 FAILs — `build_profile_payload() takes 1 positional argument but 2 were given` or similar.

- [ ] **Step 1.3: Implement `windows_filter` in `profile_builder.py`**

Add the reverse-lookup constant after `_BROWSER_EXE_NAMES`:

```python
# Reverse of _BROWSER_EXE_NAMES: browser name → exe basename
_BROWSER_NAME_TO_EXE: dict[str, str] = {v: k for k, v in _BROWSER_EXE_NAMES.items()}
# {"chrome": "chrome.exe", "edge": "msedge.exe"}
```

Change the function signature and add filtering logic:

```python
def build_profile_payload(
    cfg: dict[str, Any],
    windows_filter: "set[int] | None" = None,
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
```

- [ ] **Step 1.4: Run all profile_builder tests**

```
pytest tests/test_profile_builder.py -v
```

Expected: all pass.

- [ ] **Step 1.5: Commit**

```
git add profile_builder.py tests/test_profile_builder.py
git commit -m "feat: add windows_filter param to build_profile_payload

When windows_filter is a set of HWNDs, only those windows are saved and
browser tabs are filtered to browsers represented in the selection.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: `WindowPickerDialog` class in `settings_ui.py`

**Files:**
- Modify: `settings_ui.py`
- Test: `tests/test_settings_ui.py`

- [ ] **Step 2.1: Write failing tests**

Add a new class `TestWindowPickerDialog` to `tests/test_settings_ui.py`:

```python
class TestWindowPickerDialog:
    def _make_dialog(self, windows):
        """Create a WindowPickerDialog instance with mocked tkinter UI."""
        import settings_ui

        dlg = settings_ui.WindowPickerDialog.__new__(settings_ui.WindowPickerDialog)
        dlg._result = None
        dlg._vars = {}
        # Populate _vars as __init__ would, without touching tk
        for w in windows:
            hwnd = w.get("hwnd", 0)
            var = type("FakeVar", (), {"_value": True, "get": lambda self: self._value, "set": lambda self, v: setattr(self, "_value", v)})()
            dlg._vars[hwnd] = var
        return dlg

    def test_set_all_checks_all_vars(self):
        import settings_ui

        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Explorer", "exe": "explorer.exe"},
        ]
        dlg = self._make_dialog(windows)
        dlg._set_all(False)
        assert all(not v.get() for v in dlg._vars.values())
        dlg._set_all(True)
        assert all(v.get() for v in dlg._vars.values())

    def test_set_group_only_affects_group_windows(self):
        import settings_ui

        windows = [
            {"hwnd": 101, "title": "Win1", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Win2", "exe": "notepad.exe"},
            {"hwnd": 103, "title": "Win3", "exe": "explorer.exe"},
        ]
        dlg = self._make_dialog(windows)
        group = [windows[0], windows[1]]
        dlg._set_group(group, False)
        assert not dlg._vars[101].get()
        assert not dlg._vars[102].get()
        assert dlg._vars[103].get()  # unaffected

    def test_save_returns_checked_hwnds(self):
        import settings_ui

        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Explorer", "exe": "explorer.exe"},
        ]
        dlg = self._make_dialog(windows)
        # Uncheck hwnd 102
        dlg._vars[102].set(False)

        # _save needs _dlg.destroy — patch it
        dlg._dlg = type("FakeToplevel", (), {"destroy": lambda self: None})()
        dlg._save()

        assert dlg._result == {101}

    def test_cancel_returns_none(self):
        import settings_ui

        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        dlg = self._make_dialog(windows)
        dlg._dlg = type("FakeToplevel", (), {"destroy": lambda self: None})()
        dlg._cancel()

        assert dlg._result is None

    def test_save_empty_selection_returns_empty_set(self):
        import settings_ui

        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        dlg = self._make_dialog(windows)
        dlg._vars[101].set(False)
        dlg._dlg = type("FakeToplevel", (), {"destroy": lambda self: None})()
        dlg._save()

        assert dlg._result == set()
```

- [ ] **Step 2.2: Run tests to verify they fail**

```
pytest tests/test_settings_ui.py::TestWindowPickerDialog -v
```

Expected: all fail — `AttributeError: module 'settings_ui' has no attribute 'WindowPickerDialog'`.

- [ ] **Step 2.3: Implement `WindowPickerDialog` in `settings_ui.py`**

Add `import capture` to the imports block (after `import browser_runtime`):

```python
import capture
```

Add the class just before `class SettingsWindow:`:

```python
class WindowPickerDialog:
    """Modal dialog for selecting which windows to include in a saved profile.

    Usage::

        picker = WindowPickerDialog(parent, windows)
        selected_hwnds = picker.result  # set[int] or None if cancelled
    """

    def __init__(self, parent: tk.Misc, windows: list[dict]) -> None:
        self._result: set[int] | None = None
        self._vars: dict[int, tk.BooleanVar] = {}

        self._dlg = tk.Toplevel(parent)
        self._dlg.title("Select windows to save")
        self._dlg.resizable(False, False)
        self._dlg.grab_set()

        self._build(windows)
        parent.wait_window(self._dlg)

    def _build(self, windows: list[dict]) -> None:
        # Group windows by exe basename
        groups: dict[str, list[dict]] = {}
        for w in windows:
            exe = os.path.basename(w.get("exe", "")).lower() or "unknown"
            groups.setdefault(exe, []).append(w)

        container = ttk.Frame(self._dlg, padding=8)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, width=460, height=400)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Global select / deselect
        top_bar = ttk.Frame(scroll_frame)
        top_bar.pack(fill="x", padx=4, pady=(4, 8))
        ttk.Button(top_bar, text="Select all", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(top_bar, text="Deselect all", command=lambda: self._set_all(False)).pack(
            side="left", padx=(4, 0)
        )

        # Per-group sections
        for exe_name, wins in sorted(groups.items()):
            grp = ttk.LabelFrame(scroll_frame, text=exe_name, padding=4)
            grp.pack(fill="x", padx=4, pady=4)

            hdr = ttk.Frame(grp)
            hdr.pack(fill="x")
            ttk.Button(
                hdr, text="Deselect all", command=lambda ws=wins: self._set_group(ws, False)
            ).pack(side="right")
            ttk.Button(
                hdr, text="Select all", command=lambda ws=wins: self._set_group(ws, True)
            ).pack(side="right", padx=(0, 4))

            for w in wins:
                hwnd = w.get("hwnd", 0)
                var = tk.BooleanVar(value=True)
                self._vars[hwnd] = var
                title = w.get("title", "") or f"(hwnd={hwnd})"
                ttk.Checkbutton(grp, text=title, variable=var).pack(anchor="w", padx=8)

        # Save / Cancel buttons
        btn_frame = ttk.Frame(self._dlg, padding=8)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="right", padx=(0, 4))

    def _set_all(self, value: bool) -> None:
        for var in self._vars.values():
            var.set(value)

    def _set_group(self, wins: list[dict], value: bool) -> None:
        for w in wins:
            hwnd = w.get("hwnd", 0)
            if hwnd in self._vars:
                self._vars[hwnd].set(value)

    def _save(self) -> None:
        self._result = {hwnd for hwnd, var in self._vars.items() if var.get()}
        self._dlg.destroy()

    def _cancel(self) -> None:
        self._result = None
        self._dlg.destroy()

    @property
    def result(self) -> "set[int] | None":
        return self._result
```

- [ ] **Step 2.4: Run dialog tests**

```
pytest tests/test_settings_ui.py::TestWindowPickerDialog -v
```

Expected: all 5 pass.

- [ ] **Step 2.5: Run full test suite to check for regressions**

```
pytest tests/ -v
```

Expected: all existing tests still pass.

- [ ] **Step 2.6: Commit**

```
git add settings_ui.py tests/test_settings_ui.py
git commit -m "feat: add WindowPickerDialog to settings_ui

Groups capturable windows by app with per-group and global
select/deselect controls. Returns set[int] of selected HWNDs.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: `_save_selected_layout` method + button split

**Files:**
- Modify: `settings_ui.py`
- Test: `tests/test_settings_ui.py`

- [ ] **Step 3.1: Write failing tests**

Add a new class `TestSaveSelectedLayout` to `tests/test_settings_ui.py`:

```python
class TestSaveSelectedLayout:
    def _make_win(self):
        import settings_ui
        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._on_save = Mock()
        win._refresh_profiles = Mock()
        return win

    def test_save_all_calls_existing_save_layout(self):
        """'Save all' still calls the unmodified _save_layout path."""
        import settings_ui

        win = self._make_win()
        with patch.object(win, "_save_layout") as mock_save:
            win._save_layout()
        mock_save.assert_called_once()

    def test_save_selected_opens_picker_with_live_windows(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": windows, "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        mock_picker = Mock()
        mock_picker.result = {101}

        with patch("settings_ui.simpledialog.askstring", return_value="MyProfile"), \
             patch("settings_ui.capture.capture_windows", return_value=windows) as mock_capture, \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker) as mock_dlg, \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile"), \
             patch("settings_ui.prof.save_config"), \
             patch("settings_ui.messagebox.showinfo"):
            win._save_selected_layout()

        mock_capture.assert_called_once()
        mock_dlg.assert_called_once_with(win._win, windows)

    def test_save_selected_aborts_on_name_cancel(self):
        import settings_ui

        win = self._make_win()
        with patch("settings_ui.simpledialog.askstring", return_value=None), \
             patch("settings_ui.capture.capture_windows") as mock_capture, \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_capture.assert_not_called()
        mock_save_profile.assert_not_called()

    def test_save_selected_aborts_when_picker_cancelled(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        mock_picker = Mock()
        mock_picker.result = None  # user hit Cancel

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_save_profile.assert_not_called()

    def test_save_selected_passes_hwnd_filter_to_builder(self):
        import settings_ui

        win = self._make_win()
        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Edge", "exe": "msedge.exe"},
        ]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": [windows[0]], "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        mock_picker = Mock()
        mock_picker.result = {101}  # only Notepad selected

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload) as mock_build, \
             patch("settings_ui.prof.save_profile"), \
             patch("settings_ui.prof.save_config"), \
             patch("settings_ui.messagebox.showinfo"):
            win._save_selected_layout()

        mock_build.assert_called_once_with(cfg, windows_filter={101})

    def test_save_selected_aborts_when_no_windows_open(self):
        import settings_ui

        win = self._make_win()
        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=[]), \
             patch("settings_ui.messagebox.showinfo") as mock_info, \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_info.assert_called_once()
        mock_save_profile.assert_not_called()

    def test_save_selected_shows_error_when_zero_windows_checked(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        mock_picker = Mock()
        mock_picker.result = set()  # all unchecked

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.messagebox.showerror") as mock_error, \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_error.assert_called_once()
        mock_save_profile.assert_not_called()
```

- [ ] **Step 3.2: Run tests to verify they fail**

```
pytest tests/test_settings_ui.py::TestSaveSelectedLayout -v
```

Expected: FAILs — `AttributeError: 'SettingsWindow' object has no attribute '_save_selected_layout'`.

- [ ] **Step 3.3: Add `_save_selected_layout` method to `SettingsWindow`**

Add the method to `SettingsWindow` immediately after `_save_layout`:

```python
def _save_selected_layout(self) -> None:
    name = simpledialog.askstring(
        "Save layout", "Profile name:", parent=self._win
    )
    if not name or not name.strip():
        return
    name = name.strip()

    windows = capture.capture_windows()
    if not windows:
        messagebox.showinfo(
            "Nothing to save",
            "No windows are currently open.",
            parent=self._win,
        )
        return

    picker = WindowPickerDialog(self._win, windows)
    selected_hwnds = picker.result
    if selected_hwnds is None:
        return
    if not selected_hwnds:
        messagebox.showerror(
            "Nothing selected",
            "Select at least one window to save.",
            parent=self._win,
        )
        return

    try:
        cfg = prof.load_config()
        data = profile_builder.build_profile_payload(cfg, windows_filter=selected_hwnds)
    except Exception as exc:
        log.error("Save failed before profile write: %s", exc)
        messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
        return

    try:
        prof.save_profile(name, data)
    except Exception as exc:
        log.error("Save failed while writing profile '%s': %s", name, exc)
        messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
        return

    cfg["last_profile"] = name
    config_error: Exception | None = None
    try:
        prof.save_config(cfg)
    except Exception as exc:
        config_error = exc
        log.error("Profile '%s' saved, but config update failed: %s", name, exc)

    self._refresh_profiles()

    if config_error is not None:
        messagebox.showwarning(
            "Saved with warning",
            f"Profile '{name}' saved, but updating defaults failed: {config_error}",
            parent=self._win,
        )
        return

    callback_error: Exception | None = None
    try:
        self._on_save(cfg)
    except Exception as exc:
        callback_error = exc
        log.error("Profile saved but on_save callback failed: %s", exc)

    if callback_error is not None:
        messagebox.showwarning(
            "Saved with warning",
            f"Profile '{name}' saved, but refresh callback failed: {callback_error}",
            parent=self._win,
        )
    else:
        messagebox.showinfo("Saved", f"Profile '{name}' saved.", parent=self._win)
```

- [ ] **Step 3.4: Split the button in `_build_profiles_tab`**

Find this block in `settings_ui.py`:

```python
        btn_frame = ttk.Frame(left_pane)
        btn_frame.pack(fill="x", pady=(10, 6))
        for col in range(4):
            btn_frame.columnconfigure(col, weight=1)

        ttk.Button(btn_frame, text="Save current layout", command=self._save_layout).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Restore", command=self._restore_selected).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Rename", command=self._rename_selected).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).grid(
            row=0, column=3, padx=4, sticky="ew"
        )
```

Replace with:

```python
        btn_frame = ttk.Frame(left_pane)
        btn_frame.pack(fill="x", pady=(10, 6))
        for col in range(5):
            btn_frame.columnconfigure(col, weight=1)

        ttk.Button(btn_frame, text="Save all", command=self._save_layout).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Save selected…", command=self._save_selected_layout).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Restore", command=self._restore_selected).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Rename", command=self._rename_selected).grid(
            row=0, column=3, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).grid(
            row=0, column=4, padx=4, sticky="ew"
        )
```

- [ ] **Step 3.5: Run new tests**

```
pytest tests/test_settings_ui.py::TestSaveSelectedLayout -v
```

Expected: all 7 pass.

- [ ] **Step 3.6: Run full test suite**

```
pytest tests/ -v
```

Expected: all tests pass (149+ tests). Fix any failures before committing.

- [ ] **Step 3.7: Commit**

```
git add settings_ui.py tests/test_settings_ui.py
git commit -m "feat: add Save selected… button and _save_selected_layout flow

- Splits 'Save current layout' into 'Save all' and 'Save selected…'
- Name prompt first, then grouped window picker
- HWNDs forwarded to build_profile_payload(windows_filter=...)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
