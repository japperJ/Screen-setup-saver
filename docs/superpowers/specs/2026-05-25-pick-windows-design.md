# Pick Windows on Save — Design Spec

**Date:** 2026-05-25  
**Status:** Approved

---

## Overview

Add a "Save selected…" button alongside the existing "Save all" button so the user can choose exactly which windows to include in a saved profile. "Save all" is unchanged. Browser URLs are automatically filtered to match the selected windows only.

---

## User Flow

### Save all (unchanged)
1. User clicks **Save all**.
2. Name prompt appears.
3. All capturable windows + all browser tabs are saved as today.

### Save selected…
1. User clicks **Save selected…**.
2. **Name prompt** — type a profile name, click OK.
3. **Window picker** opens as a modal dialog:
   - Windows are listed **grouped by app** (exe name as section header).
   - Each window has a checkbox and shows its title.
   - Each group header has a **Select all / Deselect all** toggle.
   - A global **Select all / Deselect all** at the top of the list.
   - All windows are checked by default.
4. User unchecks unwanted windows, clicks **Save**.
5. Profile is saved with only the checked windows.
6. Browser URLs are included only for browser processes (Chrome/Edge) where at least one window from that process was selected; tabs are associated to the matched windows.

---

## UI Layout

Two buttons side-by-side replace the single "Save current layout" button in `settings_ui.py`:

```
[ Save all ]  [ Save selected… ]
```

Both buttons sit in the same grid row, same visual weight.

The picker is a `tk.Toplevel` modal:
- Fixed width (~480 px), scrollable list for tall window counts.
- Section headers in bold/subtle background.
- Checkbox per window, indented under header.
- Select all / Deselect all link per section header (right-aligned).
- Global select/deselect at top of scroll area.
- **Save** and **Cancel** buttons at the bottom.

---

## Architecture

### `settings_ui.py`

- Replace the single "Save current layout" button with two buttons: `btn_save_all` and `btn_save_selected`.
- `_save_layout()` (existing) is called by `btn_save_all` — no changes to its internals.
- New `_save_selected_layout()` method:
  1. Shows name prompt (reuse existing `simpledialog.askstring` call).
  2. Calls `capture.capture_windows()` to get the live window list.
  3. Opens `WindowPickerDialog(parent, windows)` and waits for result.
  4. If user cancels, aborts.
  5. Calls `profile_builder.build_profile_payload(cfg, windows_filter=selected_hwnds)`.
  6. Saves the profile via `profiles.save_profile(name, payload)`.
- New `WindowPickerDialog` class (inner or module-level in `settings_ui.py`):
  - `__init__(parent, windows: list[dict])` — `windows` is the list returned by `capture_windows()`.
  - Groups windows by `exe` field.
  - Returns `selected_hwnds: set[int]` or `None` if cancelled.

### `profile_builder.py`

- `build_profile_payload(cfg, windows_filter: set[int] | None = None)`:
  - If `windows_filter` is `None` — existing behaviour, all windows included.
  - If `windows_filter` is a set of HWNDs — only include windows whose `hwnd` is in the set.
  - Browser tab filtering: include tabs only for browser processes where the matched window's `pid` belongs to that browser. Each browser tab entry already carries enough process info for this (via `browser.py` returning tabs per browser type).

### `capture.py`

No changes. `capture_windows()` is called before the picker opens so the list is current.

### `browser.py` / `profile_builder.py` browser filtering

When `windows_filter` is active:
- Collect the PIDs of selected windows that belong to Chrome or Edge.
- For Chrome: include tabs only if a selected window has a Chrome PID.
- For Edge: include tabs only if a selected window has an Edge PID.
- If no Chrome windows selected → Chrome tabs omitted entirely.
- If no Edge windows selected → Edge tabs omitted entirely.
- If some Edge windows selected (but not all) → all Edge tabs are included (tab-to-window mapping at the HWND level is not available from CDP; including all tabs for that browser is the safe fallback).

---

## Data / Profile Format

No changes to the saved profile schema. A profile saved with "Save selected…" looks identical to one saved with "Save all" — it simply has fewer entries in the `windows` list and possibly fewer browser tabs. Restore logic is unaffected.

---

## Error Handling

- If `capture_windows()` returns an empty list, show a brief info message and abort — nothing to pick.
- If the user picks zero windows in the picker and clicks Save, show a brief error: "Select at least one window to save."
- If name prompt is cancelled or empty, abort silently (same as today's Save all).

---

## Testing

- `tests/test_settings_ui.py`:
  - `test_save_all_calls_existing_path` — clicking "Save all" goes through the unmodified `_save_layout` path.
  - `test_save_selected_opens_picker` — clicking "Save selected…" opens `WindowPickerDialog`.
  - `test_save_selected_aborts_on_cancel` — cancelling picker or name prompt does not save.
  - `test_save_selected_passes_filter_to_builder` — the HWNDs from the picker are forwarded to `build_profile_payload`.
  - `test_save_selected_no_windows_shows_error` — empty window list shows info message and aborts.
  - `test_save_selected_zero_selected_shows_error` — zero checkboxes checked shows error.

- `tests/test_profile_builder.py`:
  - `test_windows_filter_excludes_unselected` — filtered payload contains only selected HWNDs.
  - `test_windows_filter_none_includes_all` — `windows_filter=None` behaves as today.
  - `test_browser_tabs_excluded_when_browser_not_selected` — if no Edge HWNDs selected, Edge tabs absent.
  - `test_browser_tabs_included_when_browser_selected` — if Edge HWNDs selected, Edge tabs present.

---

## Out of Scope

- Reordering windows in the picker.
- Remembering last-used selection across saves.
- Filtering the picker list (search box).
- Picking windows from a hotkey-triggered save (hotkey always saves all).
