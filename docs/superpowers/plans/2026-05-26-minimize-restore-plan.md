# Minimize Other Windows on Restore — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Yes/No dialog at restore time allowing users to minimize all other windows before restoring a profile.

**Architecture:** New `minimize_other_windows()` function in `restore.py` enumerates and minimizes non-profile windows. Modified restore trigger in `main.py` shows dialog and calls minimize before restore.

**Tech Stack:** Windows API (win32gui, win32con, win32process), tkinter messagebox, existing restore logic

---

## File Structure

- **`restore.py`** (modify)
  - Add: `minimize_other_windows(profile: dict[str, Any]) -> None`
  - Extract exe paths from profile, enumerate windows, minimize non-matching windows
  - Reuse existing window enumeration patterns from `_find_windows_by_exe()`

- **`main.py`** (modify)
  - Find: `restore.restore_profile(profile)` call(s)
  - Add: Dialog before restore, call minimize if "Yes" chosen
  - Keep existing error handling

- **`tests/test_restore.py`** (modify)
  - Add: 5 unit tests for `minimize_other_windows()` function
  - Test: window filtering, already-minimized skip, tool window skip, error handling, multiple instances

- **`tests/test_main.py`** or equivalent (modify or create)
  - Add: 1 integration test for dialog + restore flow

---

## Task 1: Unit Tests for `minimize_other_windows()`

**Files:**
- Modify: `tests/test_restore.py`

**Context:** Write 5 failing unit tests that define the behavior of the new `minimize_other_windows()` function. These tests will guide implementation in Task 2.

- [ ] **Step 1: Write failing test — minimizes non-profile windows**

Add to end of `tests/test_restore.py` inside a new test class `TestMinimizeOtherWindows`:

```python
class TestMinimizeOtherWindows:
    def test_minimize_other_windows_minimizes_non_profile_windows(self):
        """Verify that non-profile windows are minimized, profile windows are skipped."""
        import restore
        from unittest.mock import Mock, patch, call
        
        # Profile with one notepad.exe window
        profile = {
            "windows": [
                {"exe": r"C:\Windows\System32\notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}
            ],
            "browser_tabs": {}
        }
        
        # Mock two running windows: notepad (in profile) and edge (not in profile)
        notepad_hwnd = 1001
        edge_hwnd = 1002
        
        with patch("restore.win32gui.EnumWindows") as mock_enum, \
             patch("restore.win32gui.IsIconic", return_value=False), \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId") as mock_get_pid, \
             patch("restore.win32api.OpenProcess") as mock_open, \
             patch("restore.win32process.GetModuleFileNameEx") as mock_get_exe, \
             patch("restore.win32api.CloseHandle"), \
             patch("restore.win32gui.ShowWindow") as mock_show_window, \
             patch("restore.log"):
            
            # Setup: EnumWindows calls callback with both hwnds
            def enum_callback(callback, _):
                callback(notepad_hwnd, None)
                callback(edge_hwnd, None)
                return True
            mock_enum.side_effect = enum_callback
            
            # Mock PID lookup
            mock_get_pid.side_effect = [(0, 1001), (0, 1002)]  # dummy PIDs
            
            # Mock process handles
            mock_handle = Mock()
            mock_open.return_value = mock_handle
            
            # Mock exe paths: notepad matches profile, edge doesn't
            mock_get_exe.side_effect = [
                r"C:\Windows\System32\notepad.exe",  # notepad
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"  # edge
            ]
            
            # Call function
            restore.minimize_other_windows(profile)
            
            # Assert: ShowWindow called only for edge (not notepad)
            mock_show_window.assert_called_once_with(edge_hwnd, restore.win32con.SW_MINIMIZE)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/test_restore.py::TestMinimizeOtherWindows::test_minimize_other_windows_minimizes_non_profile_windows -v
```

Expected output:
```
FAILED tests/test_restore.py::TestMinimizeOtherWindows::test_minimize_other_windows_minimizes_non_profile_windows
AttributeError: module 'restore' has no attribute 'minimize_other_windows'
```

- [ ] **Step 3: Write failing test — skips already-minimized windows**

Add to `TestMinimizeOtherWindows` class:

```python
    def test_minimize_other_windows_skips_already_minimized(self):
        """Verify that windows already minimized (IsIconic=True) are not minimized again."""
        import restore
        from unittest.mock import Mock, patch
        
        profile = {
            "windows": [
                {"exe": r"C:\Windows\System32\notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}
            ],
            "browser_tabs": {}
        }
        
        edge_hwnd = 1002
        
        with patch("restore.win32gui.EnumWindows") as mock_enum, \
             patch("restore.win32gui.IsIconic") as mock_iconic, \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId", return_value=(0, 1002)), \
             patch("restore.win32api.OpenProcess") as mock_open, \
             patch("restore.win32process.GetModuleFileNameEx", return_value=r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"), \
             patch("restore.win32api.CloseHandle"), \
             patch("restore.win32gui.ShowWindow") as mock_show_window, \
             patch("restore.log"):
            
            def enum_callback(callback, _):
                callback(edge_hwnd, None)
                return True
            mock_enum.side_effect = enum_callback
            
            # Edge window is already minimized
            mock_iconic.return_value = True
            
            mock_handle = Mock()
            mock_open.return_value = mock_handle
            
            restore.minimize_other_windows(profile)
            
            # Assert: ShowWindow never called (window already minimized)
            mock_show_window.assert_not_called()
```

- [ ] **Step 4: Run tests to verify both fail**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/test_restore.py::TestMinimizeOtherWindows -v
```

Expected: Both tests fail with AttributeError (function doesn't exist yet)

- [ ] **Step 5: Write failing test — skips tool windows**

Add to `TestMinimizeOtherWindows` class:

```python
    def test_minimize_other_windows_skips_tool_windows(self):
        """Verify that tool windows (WS_EX_TOOLWINDOW) are skipped."""
        import restore
        import win32con
        from unittest.mock import Mock, patch
        
        profile = {
            "windows": [{"exe": r"C:\Windows\System32\notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}],
            "browser_tabs": {}
        }
        
        tool_hwnd = 2001
        
        with patch("restore.win32gui.EnumWindows") as mock_enum, \
             patch("restore.win32gui.IsIconic", return_value=False), \
             patch("restore.win32gui.GetWindowLong") as mock_get_long, \
             patch("restore.win32gui.ShowWindow") as mock_show_window, \
             patch("restore.log"):
            
            def enum_callback(callback, _):
                callback(tool_hwnd, None)
                return True
            mock_enum.side_effect = enum_callback
            
            # Tool window has WS_EX_TOOLWINDOW flag set
            mock_get_long.return_value = win32con.WS_EX_TOOLWINDOW
            
            restore.minimize_other_windows(profile)
            
            # Assert: ShowWindow never called (tool window skipped before exe check)
            mock_show_window.assert_not_called()
```

- [ ] **Step 6: Write failing test — handles minimize errors gracefully**

Add to `TestMinimizeOtherWindows` class:

```python
    def test_minimize_other_windows_handles_api_errors(self):
        """Verify that ShowWindow errors are logged but don't crash the function."""
        import restore
        from unittest.mock import Mock, patch
        
        profile = {
            "windows": [{"exe": r"C:\Windows\System32\notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}],
            "browser_tabs": {}
        }
        
        edge_hwnd = 1002
        
        with patch("restore.win32gui.EnumWindows") as mock_enum, \
             patch("restore.win32gui.IsIconic", return_value=False), \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId", return_value=(0, 1002)), \
             patch("restore.win32api.OpenProcess") as mock_open, \
             patch("restore.win32process.GetModuleFileNameEx", return_value=r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"), \
             patch("restore.win32api.CloseHandle"), \
             patch("restore.win32gui.ShowWindow") as mock_show, \
             patch("restore.log") as mock_log:
            
            def enum_callback(callback, _):
                callback(edge_hwnd, None)
                return True
            mock_enum.side_effect = enum_callback
            
            mock_handle = Mock()
            mock_open.return_value = mock_handle
            
            # ShowWindow raises exception (e.g., permission denied)
            mock_show.side_effect = OSError("Access denied")
            
            # Function should not raise — should log and continue
            restore.minimize_other_windows(profile)
            
            # Assert: Error was logged
            assert mock_log.error.called
            error_msg = mock_log.error.call_args[0][0]
            assert "Failed to minimize" in error_msg
```

- [ ] **Step 7: Write failing test — ignores multiple instances of profile exe**

Add to `TestMinimizeOtherWindows` class:

```python
    def test_minimize_other_windows_ignores_multiple_instances_of_profile_exe(self):
        """Verify that all windows with profile exe are skipped, even multiple instances."""
        import restore
        from unittest.mock import Mock, patch
        
        profile = {
            "windows": [
                {"exe": r"C:\Windows\System32\notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}
            ],
            "browser_tabs": {}
        }
        
        notepad_hwnd1 = 1001
        notepad_hwnd2 = 1003  # Second notepad instance
        edge_hwnd = 1002
        
        with patch("restore.win32gui.EnumWindows") as mock_enum, \
             patch("restore.win32gui.IsIconic", return_value=False), \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId") as mock_get_pid, \
             patch("restore.win32api.OpenProcess") as mock_open, \
             patch("restore.win32process.GetModuleFileNameEx") as mock_get_exe, \
             patch("restore.win32api.CloseHandle"), \
             patch("restore.win32gui.ShowWindow") as mock_show_window, \
             patch("restore.log"):
            
            def enum_callback(callback, _):
                callback(notepad_hwnd1, None)
                callback(edge_hwnd, None)
                callback(notepad_hwnd2, None)
                return True
            mock_enum.side_effect = enum_callback
            
            mock_get_pid.side_effect = [(0, 1001), (0, 1002), (0, 1003)]
            
            mock_handle = Mock()
            mock_open.return_value = mock_handle
            
            # All notepads return same exe, edge returns different
            mock_get_exe.side_effect = [
                r"C:\Windows\System32\notepad.exe",  # notepad 1
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",  # edge
                r"C:\Windows\System32\notepad.exe",  # notepad 2
            ]
            
            restore.minimize_other_windows(profile)
            
            # Assert: Only edge minimized (both notepads skipped)
            mock_show_window.assert_called_once_with(edge_hwnd, restore.win32con.SW_MINIMIZE)
```

- [ ] **Step 8: Run all 5 tests to verify they fail**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/test_restore.py::TestMinimizeOtherWindows -v
```

Expected: All 5 tests fail with AttributeError

- [ ] **Step 9: Commit tests**

```bash
cd C:\REP\Screen-setup-saver
git add tests/test_restore.py
git commit -m "test: add unit tests for minimize_other_windows function

- Test non-profile windows are minimized
- Test already-minimized windows are skipped  
- Test tool windows are skipped
- Test API errors are handled gracefully
- Test multiple instances of profile exe are skipped

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Implement `minimize_other_windows()` Function

**Files:**
- Modify: `restore.py`

**Context:** Implement the `minimize_other_windows()` function to make all 5 unit tests pass. Reuse existing window enumeration patterns from `_find_windows_by_exe()`.

- [ ] **Step 1: Locate insertion point in restore.py**

The function should go after `_place_window()` and before `restore_browser_tabs()`, around line 160. Check:

```bash
cd C:\REP\Screen-setup-saver
grep -n "def restore_browser_tabs" restore.py
```

Expected: Shows line number (should be ~161)

- [ ] **Step 2: Add `minimize_other_windows()` function**

Insert at line 160 (before `restore_browser_tabs`):

```python
# ── Minimize other windows ───────────────────────────────────────────────────

def minimize_other_windows(profile: dict[str, Any]) -> None:
    """Minimize all visible windows except those in the profile.
    
    Enumerates all visible windows across all monitors. Skips:
    - Windows already minimized
    - Tool windows (tooltips, floating toolbars)
    - Windows whose exe path matches any exe in the profile["windows"] list
    
    If minimization fails on a window, logs error and continues.
    """
    # Extract exe paths from profile, normalized to lowercase for comparison
    profile_exes: set[str] = set()
    for window in profile.get("windows", []):
        exe = window.get("exe", "").lower()
        if exe:
            profile_exes.add(exe)
    
    if not profile_exes:
        log.debug("No profile exes found; minimize_other_windows will minimize all visible windows")
    
    minimized_count = 0
    error_count = 0
    
    def _cb(hwnd: int, _: Any) -> bool:
        nonlocal minimized_count, error_count
        
        # Skip if already minimized
        if win32gui.IsIconic(hwnd):
            return True
        
        # Skip tool windows
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return True
        
        # Get exe path of this window
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
            finally:
                win32api.CloseHandle(handle)
        except Exception as e:
            log.debug("Could not get exe for hwnd=%d: %s", hwnd, e)
            return True
        
        exe_lower = exe_path.lower()
        
        # Skip if exe is in profile
        if exe_lower in profile_exes:
            return True
        
        # Minimize this window
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            minimized_count += 1
        except Exception as e:
            log.error("Failed to minimize hwnd=%d: %s", hwnd, e)
            error_count += 1
        
        return True
    
    win32gui.EnumWindows(_cb, None)
    log.info("Minimized %d windows (%d errors)", minimized_count, error_count)
```

- [ ] **Step 3: Run tests to verify implementation**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/test_restore.py::TestMinimizeOtherWindows -v
```

Expected: All 5 tests PASS

- [ ] **Step 4: Run full test suite to verify no regressions**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/ -v --tb=line 2>&1 | Select-Object -Last 3
```

Expected: All tests pass (should be 179 or 184 depending on earlier tasks)

- [ ] **Step 5: Commit implementation**

```bash
cd C:\REP\Screen-setup-saver
git add restore.py
git commit -m "feat: implement minimize_other_windows function

- Enumerates all visible windows on all monitors
- Skips already-minimized and tool windows
- Skips windows with exe paths matching profile exes
- Logs errors but continues if minimize fails
- All 5 unit tests passing

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Unit Tests for Restore Dialog Flow

**Files:**
- Modify: `tests/test_restore.py` or create `tests/test_main.py`

**Context:** Write 2 unit tests for the restore trigger (in main.py) to verify the dialog shows and the minimize function is called appropriately.

- [ ] **Step 1: Write failing test — dialog shown and minimize called on Yes**

Add to `tests/test_restore.py` or new test class in appropriate test file:

```python
class TestRestoreDialogFlow:
    def test_restore_shows_dialog_and_minimizes_on_yes(self):
        """Verify that restore shows dialog and calls minimize when user clicks Yes."""
        import main
        from unittest.mock import Mock, patch
        
        profile_name = "TestProfile"
        profile_data = {
            "windows": [{"exe": "notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}],
            "browser_tabs": {}
        }
        
        with patch("main.prof.load_profile", return_value=profile_data), \
             patch("main.messagebox.askyesno", return_value=True) as mock_dialog, \
             patch("main.restore.minimize_other_windows") as mock_minimize, \
             patch("main.restore.restore_profile") as mock_restore:
            
            # Call restore (exact function name depends on main.py structure — adjust as needed)
            # This might be called from tray, so check actual entry point
            main._on_restore_profile(profile_name)  # Adjust function name based on actual code
            
            # Assert: Dialog was shown with correct question
            mock_dialog.assert_called_once()
            dialog_args = mock_dialog.call_args
            assert "Minimize" in str(dialog_args) or "minimize" in str(dialog_args).lower()
            
            # Assert: minimize_other_windows was called
            mock_minimize.assert_called_once_with(profile_data)
            
            # Assert: restore_profile was called
            mock_restore.assert_called_once_with(profile_data)
```

- [ ] **Step 2: Write failing test — dialog shown but minimize not called on No**

Add to same test class:

```python
    def test_restore_shows_dialog_skips_minimize_on_no(self):
        """Verify that restore skips minimize when user clicks No."""
        import main
        from unittest.mock import Mock, patch
        
        profile_name = "TestProfile"
        profile_data = {
            "windows": [{"exe": "notepad.exe", "title": "Note1", "rect": [0, 0, 800, 600], "state": "normal"}],
            "browser_tabs": {}
        }
        
        with patch("main.prof.load_profile", return_value=profile_data), \
             patch("main.messagebox.askyesno", return_value=False) as mock_dialog, \
             patch("main.restore.minimize_other_windows") as mock_minimize, \
             patch("main.restore.restore_profile") as mock_restore:
            
            # Call restore
            main._on_restore_profile(profile_name)
            
            # Assert: Dialog was shown
            mock_dialog.assert_called_once()
            
            # Assert: minimize_other_windows was NOT called
            mock_minimize.assert_not_called()
            
            # Assert: restore_profile was called normally
            mock_restore.assert_called_once_with(profile_data)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/test_restore.py::TestRestoreDialogFlow -v
```

Expected: Both tests fail (function not modified yet)

- [ ] **Step 4: Commit tests**

```bash
cd C:\REP\Screen-setup-saver
git add tests/test_restore.py
git commit -m "test: add dialog flow tests for restore

- Test dialog shown and minimize called on Yes
- Test dialog shown but minimize skipped on No

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Integrate Dialog into Restore Trigger

**Files:**
- Modify: `main.py` (check `_on_restore_profile()` or similar function)

**Context:** Modify the restore trigger to show the dialog and call `minimize_other_windows()` if user chooses Yes.

- [ ] **Step 1: Locate restore trigger in main.py**

```bash
cd C:\REP\Screen-setup-saver
grep -n "restore.restore_profile\|def.*restore" main.py | head -10
```

Find the function that calls `restore.restore_profile()`. Likely called from tray.py.

- [ ] **Step 2: Check current restore call in main.py**

View the section around the restore call:

```bash
cd C:\REP\Screen-setup-saver
grep -A 10 -B 5 "restore.restore_profile" main.py
```

Expected: See the current restore flow and where to insert dialog

- [ ] **Step 3: Add dialog and minimize call**

Modify the restore function. Find this pattern:

```python
profile = prof.load_profile(profile_name)
restore.restore_profile(profile)
```

Replace with:

```python
profile = prof.load_profile(profile_name)

# Show dialog: minimize all other windows?
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

Exact code depends on where restore is called. Check if already in main.py or if it's in tray.py.

- [ ] **Step 4: Run the 2 dialog flow tests**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/test_restore.py::TestRestoreDialogFlow -v
```

Expected: Both tests PASS

- [ ] **Step 5: Run full test suite**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/ -v --tb=line 2>&1 | Select-Object -Last 3
```

Expected: All tests pass

- [ ] **Step 6: Commit integration**

```bash
cd C:\REP\Screen-setup-saver
git add main.py
git commit -m "feat: add minimize dialog to restore trigger

- Show Yes/No dialog when restore is clicked
- Call minimize_other_windows if user chooses Yes
- Otherwise restore normally
- Dialog flow tests passing

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Manual Testing & Verification

**Files:**
- None (manual testing)

**Context:** Verify the feature works end-to-end in the running app. Test both Yes and No paths.

- [ ] **Step 1: Start the app**

```bash
cd C:\REP\Screen-setup-saver
python main.py
```

Wait for tray icon to appear.

- [ ] **Step 2: Create or load a test profile**

Using the Settings window, create a profile with some windows (e.g., Notepad and Calculator). Save as "TestRestore".

- [ ] **Step 3: Test restore with minimize (Yes path)**

- Open some unrelated windows (e.g., Notepad, Edge, File Explorer)
- In Settings, right-click the "TestRestore" profile and select "Restore" (or use tray)
- Dialog should appear: "Minimize all other windows?"
- Click "Yes, Minimize"
- Verify: All windows except the profile's saved apps are minimized to taskbar
- Verify: Profile's windows appear in their saved positions

- [ ] **Step 4: Test restore without minimize (No path)**

- Open the same unrelated windows again
- Restore "TestRestore" and click "No, Just Open"
- Verify: Unrelated windows stay visible and in place
- Verify: Profile's windows appear in their saved positions

- [ ] **Step 5: Test profile with no windows**

- Create a profile with 0 windows (empty profile)
- Open several unrelated windows
- Restore the empty profile and click "Yes"
- Verify: All windows minimize (intended behavior for empty profile)

- [ ] **Step 6: Run full test suite one final time**

```bash
cd C:\REP\Screen-setup-saver
python -m pytest tests/ -v --tb=line 2>&1 | Select-Object -Last 5
```

Expected: All tests pass (should be 184+)

- [ ] **Step 7: Commit manual testing notes (optional)**

If you want to document the testing:

```bash
cd C:\REP\Screen-setup-saver
git add -A
git commit -m "docs: manual testing verification for minimize restore feature

- Tested minimize (Yes) path: non-profile windows minimized
- Tested normal (No) path: all windows remain visible
- Tested empty profile: all windows minimized as expected
- All automated tests passing

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Verification Checklist

- [ ] All 5 unit tests for `minimize_other_windows()` pass
- [ ] All 2 dialog flow tests pass
- [ ] Full test suite passes (184+ tests)
- [ ] Manual test: Yes path minimizes non-profile windows
- [ ] Manual test: No path restores normally
- [ ] Manual test: Empty profile minimizes everything
- [ ] No regressions in existing restore functionality
- [ ] Code follows existing patterns in restore.py and main.py
