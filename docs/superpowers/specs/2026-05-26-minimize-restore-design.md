# Design: Minimize Other Windows on Restore

## Overview

When a user restores a profile, they will see a simple Yes/No dialog asking whether to minimize all other windows on all monitors. Based on their choice:
- **Yes:** Minimize all other windows (except those in the profile), then restore the profile
- **No:** Restore the profile normally without minimizing anything

This gives users control over desktop clutter at restore time without adding permanent settings.

## Requirements

1. **Dialog on Restore:**
   - Display a Yes/No dialog when user clicks "Restore" on any profile
   - Question: "Minimize all other windows?"
   - Options: "Yes, Minimize" / "No, Just Open"
   - Cancel behavior: Do not restore if dialog is closed without choosing

2. **Minimize Behavior:**
   - Minimize all **visible, non-tool windows** on **all monitors**
   - **Exclude:** Windows whose executable path matches any exe in the profile
   - Skip windows that are already minimized
   - Skip tool windows (tooltips, floating toolbars, internal browser helpers)
   - Use Windows API `ShowWindow(hwnd, SW_MINIMIZE)` to minimize

3. **Restore Order:**
   - First minimize other windows (if user chose Yes)
   - Then proceed with normal profile restoration (launch/reposition profile windows)
   - Profile windows should appear in front after restore completes

4. **Error Handling:**
   - If minimize fails on a window: log error, continue (don't block restore)
   - If restore_profile() fails: restore is already captured by existing error handling
   - Dialog should not crash if profile loading fails

## Architecture

### New Function: `minimize_other_windows(profile: dict[str, Any]) -> None`

**Location:** `restore.py`

**Behavior:**
1. Extract all exe paths from profile["windows"] into a set (normalized to lowercase)
2. Enumerate all visible windows via `win32gui.EnumWindows()`
3. For each window:
   - Skip if already minimized (check `IsIconic(hwnd)`)
   - Skip if tool window (check `GWL_EXSTYLE & WS_EX_TOOLWINDOW`)
   - Get process exe path (same logic as `_find_windows_by_exe()`)
   - If exe path NOT in profile exes set: minimize via `ShowWindow(hwnd, SW_MINIMIZE)`
4. Log minimized window count and any errors

**Error handling:**
```python
try:
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
except Exception as e:
    log.error("Failed to minimize hwnd=%d: %s", hwnd, e)
    # Continue, don't block
```

### Modified Restore Flow

**Location:** `main.py` or `tray.py` (wherever Restore is triggered)

**Current flow:**
```python
profile = prof.load_profile(profile_name)
restore.restore_profile(profile)
```

**New flow:**
```python
profile = prof.load_profile(profile_name)

# Show dialog
from tkinter import messagebox
result = messagebox.askyesno(
    "Restore Profile",
    "Minimize all other windows?",
    icon=messagebox.QUESTION
)

# If Yes, minimize others first
if result:
    restore.minimize_other_windows(profile)

# Then restore profile (existing behavior)
restore.restore_profile(profile)
```

**Dialog details:**
- Modal, blocking (user must choose before restore proceeds)
- Yes/No buttons with labels: "Yes, Minimize" / "No, Just Open"
- Question text: "Minimize all other windows?"
- If user closes dialog (X button) or clicks outside: treated as "No" (by default behavior of `askyesno`)

**Alternative behavior:** Could treat X-close as "Cancel" (no restore), but `askyesno` returns `None` on close, which we interpret as "No" for simplicity.

## Testing Strategy

### Unit Tests (in `tests/test_restore.py`)

**Test 1: `test_minimize_other_windows_minimizes_non_profile_windows`**
- Setup: Mock profile with exe "notepad.exe"
- Mock two running windows: one notepad, one edge
- Action: Call `minimize_other_windows(profile)`
- Assert: Only edge window was minimized, notepad was skipped

**Test 2: `test_minimize_other_windows_skips_already_minimized`**
- Setup: Mock window that is already minimized (IsIconic returns True)
- Action: Call `minimize_other_windows(profile)` 
- Assert: Window was not passed to ShowWindow (already minimized, skip)

**Test 3: `test_minimize_other_windows_skips_tool_windows`**
- Setup: Mock tool window (WS_EX_TOOLWINDOW flag set)
- Action: Call `minimize_other_windows(profile)`
- Assert: Tool window was not minimized

**Test 4: `test_minimize_other_windows_handles_api_errors`**
- Setup: Mock ShowWindow to raise exception
- Action: Call `minimize_other_windows(profile)`
- Assert: Error logged, function completes (doesn't crash)

**Test 5: `test_minimize_other_windows_ignores_multiple_instances`**
- Setup: Profile with one notepad entry, two notepad windows running
- Action: Call `minimize_other_windows(profile)`
- Assert: Both notepad windows skipped (both match profile exe), other windows minimized

### Integration Tests (in `tests/test_restore.py`)

**Test 6: `test_restore_with_minimize_choice_minimizes_then_restores`**
- Setup: Mock profile with window entries
- Action: Call minimize, then call restore_profile
- Assert: Other windows minimized, profile windows appear in expected positions

## Data Flow

```
User clicks Restore
    ↓
Load profile from disk
    ↓
Show dialog: "Minimize all other windows?"
    ↓
┌─ Yes ─────────────────────────────────┐
│ minimize_other_windows(profile)        │
│   - Filter windows by profile exes     │
│   - ShowWindow(hwnd, SW_MINIMIZE)      │
└─────────────────────────────────────────┘
    ↓
restore_profile(profile)
    - Launch/reposition windows
    - Restore browser tabs
    - Bring profile windows to front
    ↓
Restore complete
```

## Edge Cases & Constraints

1. **Multiple monitors:** Enumerate all windows on all monitors (not just primary)
2. **Admin windows:** ShowWindow may fail on elevated windows; log and continue
3. **Virtual desktops (Win11):** Minimize only affects current virtual desktop; other virtual desktops are unaffected (acceptable behavior)
4. **Profile with no windows:** minimize_other_windows will minimize everything (intended behavior)
5. **Browser tabs:** minimize_other_windows only handles window-level minimize; browser tabs are restored after in restore_profile()
6. **Same exe, multiple instances:** All windows with profile's exe are preserved; others are minimized

## Out of Scope

- "Remember my choice" feature (can be added later if users request)
- Per-profile settings for default choice (can be added later)
- Restore windows from previous state (beyond current restore_profile behavior)
- Support for custom minimize behavior (e.g., move off-screen)

## Testing Verification Checklist

- [ ] Dialog shows correctly when Restore is clicked
- [ ] "Yes, Minimize" minimizes non-profile windows
- [ ] "No, Just Open" skips minimize and restores normally
- [ ] Dialog close (X button) is treated as "No"
- [ ] Minimize errors don't block restore
- [ ] All 179 existing tests still pass
- [ ] New minimize_other_windows tests pass (4+ unit tests)
- [ ] Integration test passes (minimize + restore)
