# Edit JSON Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to right-click a saved profile and edit its raw JSON inline in the Settings window's right panel, with validation before saving.

**Architecture:** All changes are in `settings_ui.py`. The right panel of the Profiles tab toggles between two states — *details mode* (existing read-only Text) and *edit mode* (new editable Text + Save/Cancel buttons). A `tk.Menu` context menu on the Treeview triggers the switch. Only `settings_ui.py` and its tests change.

**Tech Stack:** Python 3, tkinter (`tk.Text`, `tk.Menu`, `ttk.Label`, `ttk.Frame`, `pack_forget`/`pack`), `json`, `profiles` module (`load_profile`, `save_profile`).

---

### Task 1: Right-click context menu on profile Treeview

**Files:**
- Modify: `settings_ui.py` (in `_build_profiles_tab` and new `_on_profile_right_click` + `_edit_json_selected` methods)
- Test: `tests/test_settings_ui.py` (add `TestEditJsonUI` class)

This task adds the right-click menu binding and wires it to a stub `_show_json_editor`. The inline editor itself is built in Task 2.

**Background — how `SettingsWindow` works:**

`SettingsWindow` is never instantiated with a real Tk root in tests. Tests bypass `__init__` using:
```python
win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
```
then set attributes directly. All UI methods (`_refresh_profiles`, `_selected_profile`, etc.) are patched or stubbed.

`self._profile_list` is a `ttk.Treeview`. `self._win` is the `tk.Toplevel`.

**Right-click menu design:**

- Bind `<Button-3>` on `self._profile_list` to `self._on_profile_right_click`
- `_on_profile_right_click(event)` selects the item under the cursor (via `identify_row`), then posts a `tk.Menu` at the cursor position
- Menu entries: Restore, Rename, Delete, separator, Edit JSON
- `_edit_json_selected()` gets the selected profile name and calls `self._show_json_editor(name)`

- [ ] **Step 1: Write the failing tests**

Add a new class `TestEditJsonUI` in `tests/test_settings_ui.py`:

```python
class TestEditJsonUI:
    def _make_win(self):
        import settings_ui
        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = Mock()
        win._profile_list = Mock()
        win._profile_list.selection.return_value = ("item1",)
        win._profile_list.item.return_value = {"values": ("MyProfile",)}
        return win

    def test_edit_json_selected_calls_show_json_editor(self):
        import settings_ui
        win = self._make_win()
        win._show_json_editor = Mock()
        win._edit_json_selected()
        win._show_json_editor.assert_called_once_with("MyProfile")

    def test_edit_json_selected_no_op_when_no_selection(self):
        import settings_ui
        win = self._make_win()
        win._profile_list.selection.return_value = ()
        win._show_json_editor = Mock()
        win._edit_json_selected()
        win._show_json_editor.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_settings_ui.py::TestEditJsonUI -v
```
Expected: FAIL — `AttributeError: _edit_json_selected`

- [ ] **Step 3: Add `_on_profile_right_click` and `_edit_json_selected` to `SettingsWindow`**

In `settings_ui.py`, add after `_on_profile_select`:

```python
def _on_profile_right_click(self, event: object) -> None:
    # Select the row under the cursor before posting the menu
    row = self._profile_list.identify_row(event.y)  # type: ignore[attr-defined]
    if row:
        self._profile_list.selection_set(row)
    name = self._selected_profile()
    menu = tk.Menu(self._win, tearoff=0)
    menu.add_command(label="Restore", command=self._restore_selected)
    menu.add_command(label="Rename", command=self._rename_selected)
    menu.add_command(label="Delete", command=self._delete_selected)
    menu.add_separator()
    edit_state = "normal" if name else "disabled"
    menu.add_command(label="Edit JSON", command=self._edit_json_selected, state=edit_state)
    try:
        menu.tk_popup(event.x_root, event.y_root)  # type: ignore[attr-defined]
    finally:
        menu.grab_release()

def _edit_json_selected(self) -> None:
    name = self._selected_profile()
    if not name:
        return
    self._show_json_editor(name)
```

- [ ] **Step 4: Bind `<Button-3>` in `_build_profiles_tab`**

In `_build_profiles_tab`, after the existing `<<TreeviewSelect>>` binding line:
```python
self._profile_list.bind("<<TreeviewSelect>>", self._on_profile_select)
```
add:
```python
self._profile_list.bind("<Button-3>", self._on_profile_right_click)
```

Also add a stub so the tests don't crash importing:
```python
def _show_json_editor(self, name: str) -> None:
    pass  # implemented in Task 2
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_settings_ui.py::TestEditJsonUI -v
```
Expected: 2 passed

- [ ] **Step 6: Run full suite**

```
pytest tests/ -q --tb=short
```
Expected: 170 passed (168 + 2 new)

- [ ] **Step 7: Commit**

```
git add settings_ui.py tests/test_settings_ui.py
git commit -m "feat: add right-click context menu with Edit JSON entry"
```

---

### Task 2: Inline JSON editor panel (show/hide + populate)

**Files:**
- Modify: `settings_ui.py` — `_build_profiles_tab` (store refs, build edit frame), `_show_json_editor`, `_cancel_json_edit`
- Test: `tests/test_settings_ui.py` — extend `TestEditJsonUI`

**Design — panel switching:**

`_build_profiles_tab` currently packs `details_frame` (LabelFrame) into `right_pane`. We need a second frame (`_edit_frame`) that starts hidden. Switching is done with `pack_forget()` and `pack()`.

Store these new instance attributes (set during `_build_profiles_tab`):
- `self._details_frame` — the existing `details_frame` LabelFrame
- `self._right_pane` — the right pane Frame
- `self._edit_frame` — new LabelFrame for the JSON editor
- `self._json_editor` — `tk.Text` widget (editable, monospace)
- `self._json_error_label` — `ttk.Label` (red, hidden initially)
- `self._editing_profile: str | None = None`

`_show_json_editor(name)`:
1. Load the profile via `prof.load_profile(name)`
2. Pretty-print: `json.dumps(data, indent=2, ensure_ascii=False)`
3. Set `self._editing_profile = name`
4. Populate `self._json_editor` with the JSON text
5. Clear `self._json_error_label`
6. `self._details_frame.pack_forget()`
7. `self._edit_frame.pack(fill="both", expand=True)`
8. Disable `self._profile_list` (`state="disabled"`)

`_cancel_json_edit()`:
1. `self._edit_frame.pack_forget()`
2. `self._details_frame.pack(fill="both", expand=True)`
3. `self._editing_profile = None`
4. Re-enable `self._profile_list` (`state="normal"`)
5. Call `self._on_profile_select()` to restore details text

- [ ] **Step 1: Write the failing tests**

Add to `TestEditJsonUI`:

```python
def _make_win_with_panels(self):
    import settings_ui
    win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
    win._win = Mock()
    win._profile_list = Mock()
    win._profile_list.selection.return_value = ("item1",)
    win._profile_list.item.return_value = {"values": ("MyProfile",)}
    win._details_frame = Mock()
    win._edit_frame = Mock()
    win._json_editor = Mock()
    win._json_error_label = Mock()
    win._editing_profile = None
    win._on_profile_select = Mock()
    return win

def test_show_json_editor_populates_editor_and_swaps_panel(self):
    import settings_ui
    win = self._make_win_with_panels()
    profile_data = {"name": "MyProfile", "windows": [], "browser_tabs": {}}
    with patch("settings_ui.prof.load_profile", return_value=profile_data) as mock_load:
        win._show_json_editor("MyProfile")
    mock_load.assert_called_once_with("MyProfile")
    assert win._editing_profile == "MyProfile"
    # editor populated
    win._json_editor.delete.assert_called_once_with("1.0", "end")
    win._json_editor.insert.assert_called_once()
    inserted_text = win._json_editor.insert.call_args[0][1]
    import json
    assert json.loads(inserted_text) == profile_data
    # panel swap
    win._details_frame.pack_forget.assert_called_once()
    win._edit_frame.pack.assert_called_once()
    # list disabled
    win._profile_list.config.assert_called_with(state="disabled")

def test_cancel_json_edit_restores_details_panel(self):
    import settings_ui
    win = self._make_win_with_panels()
    win._editing_profile = "MyProfile"
    win._cancel_json_edit()
    win._edit_frame.pack_forget.assert_called_once()
    win._details_frame.pack.assert_called_once()
    assert win._editing_profile is None
    win._profile_list.config.assert_called_with(state="normal")
    win._on_profile_select.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_settings_ui.py::TestEditJsonUI::test_show_json_editor_populates_editor_and_swaps_panel tests/test_settings_ui.py::TestEditJsonUI::test_cancel_json_edit_restores_details_panel -v
```
Expected: FAIL — `AttributeError: _show_json_editor` (stub exists but does nothing)

- [ ] **Step 3: Update `_build_profiles_tab` to store new refs and build the edit frame**

In `settings_ui.py`, update `_build_profiles_tab`. Replace:
```python
details_frame = ttk.LabelFrame(right_pane, text="Selected profile details", padding=8)
details_frame.pack(fill="both", expand=True)
```
With:
```python
self._right_pane = right_pane
self._editing_profile = None

details_frame = ttk.LabelFrame(right_pane, text="Selected profile details", padding=8)
details_frame.pack(fill="both", expand=True)
self._details_frame = details_frame
```

After the `self._refresh_profiles()` call at the end of `_build_profiles_tab`, add:
```python
# Build the JSON edit panel (initially hidden)
edit_frame = ttk.LabelFrame(right_pane, text="Edit JSON", padding=8)
self._edit_frame = edit_frame
# editor Text
editor_scroll = ttk.Scrollbar(edit_frame, orient="vertical")
self._json_editor = tk.Text(
    edit_frame,
    height=12,
    wrap="none",
    font=("Consolas", 10),
    yscrollcommand=editor_scroll.set,
)
editor_scroll.config(command=self._json_editor.yview)
self._json_editor.pack(side="left", fill="both", expand=True)
editor_scroll.pack(side="right", fill="y")
# error label
self._json_error_label = ttk.Label(edit_frame, text="", foreground="red", wraplength=320)
self._json_error_label.pack(anchor="w", pady=(4, 0))
# Save / Cancel buttons
btn_row = ttk.Frame(edit_frame)
btn_row.pack(fill="x", pady=(6, 0))
ttk.Button(btn_row, text="Save", command=self._save_json_edit).pack(side="right", padx=(4, 0))
ttk.Button(btn_row, text="Cancel", command=self._cancel_json_edit).pack(side="right")
```

- [ ] **Step 4: Implement `_show_json_editor` and `_cancel_json_edit`**

Replace the stub `_show_json_editor` and add `_cancel_json_edit` in `settings_ui.py`:

```python
def _show_json_editor(self, name: str) -> None:
    import json as _json
    try:
        data = prof.load_profile(name)
    except Exception as exc:
        log.error("Cannot open JSON editor for %r: %s", name, exc)
        messagebox.showerror("Error", f"Failed to load profile: {exc}", parent=self._win)
        return
    self._editing_profile = name
    raw = _json.dumps(data, indent=2, ensure_ascii=False)
    self._json_editor.config(state="normal")
    self._json_editor.delete("1.0", "end")
    self._json_editor.insert("1.0", raw)
    self._json_error_label.config(text="")
    self._details_frame.pack_forget()
    self._edit_frame.pack(fill="both", expand=True)
    self._profile_list.config(state="disabled")

def _cancel_json_edit(self) -> None:
    self._edit_frame.pack_forget()
    self._details_frame.pack(fill="both", expand=True)
    self._editing_profile = None
    self._profile_list.config(state="normal")
    self._on_profile_select()
```

Also add `import json as _json` at the top of `settings_ui.py` (module level — add `import json` to the existing imports block).

- [ ] **Step 5: Run tests**

```
pytest tests/test_settings_ui.py::TestEditJsonUI -v
```
Expected: 4 passed

- [ ] **Step 6: Run full suite**

```
pytest tests/ -q --tb=short
```
Expected: 172 passed

- [ ] **Step 7: Commit**

```
git add settings_ui.py tests/test_settings_ui.py
git commit -m "feat: add inline JSON editor panel with show/cancel"
```

---

### Task 3: Save JSON with validation

**Files:**
- Modify: `settings_ui.py` — implement `_save_json_edit`
- Test: `tests/test_settings_ui.py` — extend `TestEditJsonUI`

`_save_json_edit()`:
1. Read text from `self._json_editor` (`get("1.0", "end-1c")`)
2. `json.loads(text)` — if `JSONDecodeError`: set `self._json_error_label` text and return
3. If valid: call `prof.save_profile(self._editing_profile, parsed_data)`
4. Call `_cancel_json_edit()` to return to details mode (which re-selects and refreshes)

- [ ] **Step 1: Write the failing tests**

Add to `TestEditJsonUI`:

```python
def test_save_json_valid_saves_and_returns_to_details(self):
    import settings_ui
    win = self._make_win_with_panels()
    win._editing_profile = "MyProfile"
    valid_json = '{"name": "MyProfile", "windows": [], "browser_tabs": {}}'
    win._json_editor.get = Mock(return_value=valid_json)
    win._cancel_json_edit = Mock()
    with patch("settings_ui.prof.save_profile") as mock_save:
        win._save_json_edit()
    import json
    mock_save.assert_called_once_with("MyProfile", json.loads(valid_json))
    win._json_error_label.config.assert_not_called()
    win._cancel_json_edit.assert_called_once()

def test_save_json_invalid_shows_error_and_does_not_save(self):
    import settings_ui
    win = self._make_win_with_panels()
    win._editing_profile = "MyProfile"
    win._json_editor.get = Mock(return_value="{ NOT VALID JSON !!!")
    win._cancel_json_edit = Mock()
    with patch("settings_ui.prof.save_profile") as mock_save:
        win._save_json_edit()
    mock_save.assert_not_called()
    win._cancel_json_edit.assert_not_called()
    # error label updated
    win._json_error_label.config.assert_called_once()
    error_text = win._json_error_label.config.call_args[1].get("text", "")
    assert len(error_text) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_settings_ui.py::TestEditJsonUI::test_save_json_valid_saves_and_returns_to_details tests/test_settings_ui.py::TestEditJsonUI::test_save_json_invalid_shows_error_and_does_not_save -v
```
Expected: FAIL — `AttributeError: _save_json_edit`

- [ ] **Step 3: Implement `_save_json_edit`**

Add to `settings_ui.py` after `_cancel_json_edit`:

```python
def _save_json_edit(self) -> None:
    import json as _json
    raw = self._json_editor.get("1.0", "end-1c")
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as exc:
        self._json_error_label.config(text=f"Invalid JSON: {exc}")
        return
    try:
        prof.save_profile(self._editing_profile, data)
    except Exception as exc:
        log.error("Failed to save edited JSON for %r: %s", self._editing_profile, exc)
        messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
        return
    self._cancel_json_edit()
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_settings_ui.py::TestEditJsonUI -v
```
Expected: 6 passed (all `TestEditJsonUI` tests)

- [ ] **Step 5: Run full suite**

```
pytest tests/ -q --tb=short
```
Expected: 174 passed

- [ ] **Step 6: Commit**

```
git add settings_ui.py tests/test_settings_ui.py
git commit -m "feat: implement _save_json_edit with JSON validation"
```
