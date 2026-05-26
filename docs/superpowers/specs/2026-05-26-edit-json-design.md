# Edit JSON Feature — Design Spec

**Date:** 2026-05-26  
**Status:** Approved

## Overview

Allow users to view and edit the raw JSON of a saved profile directly inside the Settings window. Useful for manual corrections — editing window titles, URLs, positions, or removing stale entries — without leaving the app.

## User Flow

1. User right-clicks a profile name in the profile list.
2. A context menu appears with: **Restore**, **Rename**, **Delete**, *(separator)*, **Edit JSON**.
3. User clicks **Edit JSON**.
4. The right panel (currently showing profile details) switches to an inline JSON editor showing the full raw JSON of the selected profile.
5. User edits the JSON freely.
6. **Save**: Validates the JSON. If invalid, shows an inline error message and does not save. If valid, overwrites the profile on disk, refreshes the profile list, and returns the right panel to the normal details view.
7. **Cancel**: Discards edits, returns right panel to the normal details view.

## UI Details

### Right-click context menu
- Bound to the `<TreeviewSelect>` + right-click (`<Button-3>`) on the profile `Treeview`.
- Menu items: Restore | Rename | Delete | *(separator)* | Edit JSON
- Menu uses `tk.Menu(tearoff=0)` and is posted at the cursor position.
- Existing "Restore", "Rename", "Delete" buttons in the button bar remain unchanged.

### Inline JSON editor (right panel)
- Replaces the read-only `tk.Text` details widget with an editable `tk.Text` widget (or uses the existing widget made editable temporarily).
- Implementation approach: toggle the right panel between two states — **details mode** (read-only `Text`) and **edit mode** (editable `Text` + Save/Cancel buttons). Use `pack_forget` / `pack` to swap.
- The editor shows the full pretty-printed JSON (`json.dumps(data, indent=2, ensure_ascii=False)`).
- Font: monospace (e.g. `("Courier New", 10)` or `("Consolas", 10)`).
- Save and Cancel buttons appear below the editor, right-aligned.

### Validation
- On Save click: attempt `json.loads(editor_text)`.
- If `json.JSONDecodeError`: show an inline error label below the editor with the parse error message. Do **not** save. Editor stays open.
- If valid: call `profiles.save_profile(name, parsed_data)`, refresh the profile list, switch back to details mode, re-select the profile.

### Error display
- A `ttk.Label` with red foreground below the editor, initially hidden.
- Set visible with the parse error text on validation failure; cleared when user resumes editing or cancels.

## Components Changed

| File | Change |
|---|---|
| `settings_ui.py` | Add right-click context menu binding to profile Treeview; add `_edit_json_selected()` method; add `_show_json_editor(name)` method; add `_save_json_edit()` method; add `_cancel_json_edit()` method; manage right-panel mode toggling |

No changes required to `profiles.py`, `capture.py`, `restore.py`, or any other module.

## State Management

- `self._editing_profile: str | None` — name of the profile currently being edited, or `None`.
- When in edit mode, selecting a different profile in the list is disabled (or triggers a "Save or cancel first" prompt — simpler: just disable the list while editing).

## Edge Cases

- **Profile deleted externally while editing**: on Save, `save_profile` will create a new file — this is acceptable behaviour.
- **Empty selection**: "Edit JSON" menu item is only shown/enabled when a profile is selected.
- **Very large profiles**: the `Text` widget handles large content fine; no pagination needed.

## Testing

- `TestEditJsonUI` in `tests/test_settings_ui.py`:
  - `test_edit_json_shows_editor_panel` — calling `_show_json_editor("name")` switches panel to edit mode and populates the text widget with the profile JSON.
  - `test_save_json_valid_saves_and_returns_to_details` — valid JSON save calls `save_profile` and switches back to details mode.
  - `test_save_json_invalid_shows_error` — invalid JSON shows error label, does not call `save_profile`.
  - `test_cancel_json_edit_returns_to_details` — cancel discards edits and switches back to details mode.
  - `test_right_click_menu_calls_edit_json` — right-clicking a selected profile and choosing Edit JSON calls `_show_json_editor`.
