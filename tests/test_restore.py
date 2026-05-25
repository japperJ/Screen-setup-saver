"""Tests for restore.py — app launching, window placement, browser tab restoration."""

import sys
from unittest.mock import MagicMock, patch, call
import pytest


class TestFindWindowsByExe:
    def test_returns_matching_hwnds(self):
        import restore
        import win32con
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        def fake_enum(cb, extra):
            cb(1, None)
            cb(2, None)
            return True

        mock_handle = MagicMock()
        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32gui.GetWindowText", return_value="Notepad"), \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId", return_value=(0, 123)), \
             patch("restore.win32api.OpenProcess", return_value=mock_handle), \
             patch("restore.win32process.GetModuleFileNameEx", return_value=r"C:\Windows\notepad.exe"), \
             patch("restore.win32api.CloseHandle"):
            result = restore._find_windows_by_exe(r"C:\Windows\notepad.exe")

        assert result == [1, 2]

    def test_case_insensitive_match(self):
        import restore
        import win32con
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        mock_handle = MagicMock()
        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32gui.GetWindowText", return_value="Notepad"), \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId", return_value=(0, 123)), \
             patch("restore.win32api.OpenProcess", return_value=mock_handle), \
             patch("restore.win32process.GetModuleFileNameEx", return_value=r"C:\Windows\NOTEPAD.EXE"), \
             patch("restore.win32api.CloseHandle"):
            result = restore._find_windows_by_exe(r"c:\windows\notepad.exe")

        assert result == [1]

    def test_skips_invisible_windows(self):
        import restore

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=False):
            result = restore._find_windows_by_exe(r"C:\notepad.exe")
        assert result == []

    def test_skips_empty_title_windows(self):
        """Transient startup windows (empty title) must not be returned."""
        import restore

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32gui.GetWindowText", return_value="   "):
            result = restore._find_windows_by_exe(r"C:\notepad.exe")
        assert result == []

    def test_skips_tool_windows(self):
        """Tool windows (WS_EX_TOOLWINDOW) are internal helpers, not user-facing windows."""
        import restore
        import win32con

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32gui.GetWindowText", return_value="Helper"), \
             patch("restore.win32gui.GetWindowLong", return_value=win32con.WS_EX_TOOLWINDOW):
            result = restore._find_windows_by_exe(r"C:\notepad.exe")
        assert result == []

    def test_handles_access_error_gracefully(self):
        import restore

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32gui.GetWindowText", return_value="Some Window"), \
             patch("restore.win32gui.GetWindowLong", return_value=0), \
             patch("restore.win32process.GetWindowThreadProcessId", side_effect=Exception("access denied")):
            result = restore._find_windows_by_exe(r"C:\notepad.exe")
        assert result == []


class TestPickHwnd:
    def test_prefers_saved_hwnd_when_unassigned(self):
        import restore
        assert restore._pick_hwnd([1, 2, 3], saved_hwnd=2, assigned=set()) == 2

    def test_skips_saved_hwnd_if_already_assigned(self):
        import restore
        assert restore._pick_hwnd([1, 2, 3], saved_hwnd=2, assigned={2}) == 1

    def test_picks_first_unassigned_when_no_saved_hwnd(self):
        import restore
        assert restore._pick_hwnd([1, 2, 3], saved_hwnd=None, assigned={1}) == 2

    def test_returns_none_when_all_assigned(self):
        import restore
        assert restore._pick_hwnd([1, 2], saved_hwnd=None, assigned={1, 2}) is None

    def test_saved_hwnd_not_in_existing_falls_back(self):
        import restore
        # saved hwnd is gone — pick first unassigned
        assert restore._pick_hwnd([1, 2], saved_hwnd=99, assigned=set()) == 1


class TestApplyPlacement:
    def _setup_con(self):
        import win32con
        win32con.SW_RESTORE = 9
        win32con.SW_SHOWNORMAL = 1
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2
        win32con.SWP_NOACTIVATE = 0x0010
        win32con.SWP_NOZORDER = 0x0004
        win32con.HWND_TOP = 0

    def test_normal_state_uses_setwindowpos(self):
        import restore
        self._setup_con()

        # GetWindowRect returns matching position → placement confirmed on first attempt
        with patch("restore.win32gui.ShowWindow") as mock_show, \
             patch("restore.win32gui.SetWindowPos") as mock_pos, \
             patch("restore.win32gui.SetWindowPlacement") as mock_place, \
             patch("restore.win32gui.GetWindowRect", return_value=(100, 200, 900, 800)), \
             patch("restore.time.sleep"):
            restore._apply_placement(1, [100, 200, 800, 600], "normal")

        mock_show.assert_called_once_with(1, 9)  # SW_RESTORE
        mock_pos.assert_called_once()
        args = mock_pos.call_args[0]
        assert args[1:5] == (0, 100, 200, 800)  # HWND_TOP, left, top, w
        assert args[5] == 600  # h
        mock_place.assert_not_called()  # not needed for normal state

    def test_normal_state_position_args(self):
        import restore
        self._setup_con()

        with patch("restore.win32gui.ShowWindow"), \
             patch("restore.win32gui.SetWindowPos") as mock_pos, \
             patch("restore.win32gui.SetWindowPlacement"), \
             patch("restore.win32gui.GetWindowRect", return_value=(100, 200, 900, 800)), \
             patch("restore.time.sleep"):
            restore._apply_placement(1, [100, 200, 800, 600], "normal")

        _, hwnd_top, left, top, w, h, _ = mock_pos.call_args[0]
        assert (left, top, w, h) == (100, 200, 800, 600)

    def test_maximized_state_calls_sw_maximize(self):
        import restore
        self._setup_con()
        import win32con
        win32con.SW_MAXIMIZE = 3

        show_calls = []
        # GetWindowPlacement returns SW_SHOWMAXIMIZED → confirmed
        with patch("restore.win32gui.ShowWindow", side_effect=lambda h, cmd: show_calls.append(cmd)), \
             patch("restore.win32gui.SetWindowPos"), \
             patch("restore.win32gui.SetWindowPlacement") as mock_place, \
             patch("restore.win32gui.GetWindowPlacement", return_value=(0, win32con.SW_SHOWMAXIMIZED, 0, 0, (0, 0, 0, 0))), \
             patch("restore.time.sleep"):
            restore._apply_placement(1, [0, 0, 1920, 1080], "maximized")

        assert win32con.SW_MAXIMIZE in show_calls
        mock_place.assert_not_called()

    def test_retries_on_failure(self):
        import restore
        self._setup_con()

        with patch("restore.win32gui.ShowWindow", side_effect=Exception("error")), \
             patch("restore.time.sleep") as mock_sleep:
            restore._apply_placement(1, [0, 0, 800, 600], "normal")

        assert mock_sleep.call_count == restore._PLACE_RETRIES - 1

    def test_retries_when_placement_not_confirmed(self):
        """If GetWindowRect shows wrong position, placement is retried."""
        import restore
        self._setup_con()

        # All verification attempts return wrong position → all retries fail → logs error
        with patch("restore.win32gui.ShowWindow"), \
             patch("restore.win32gui.SetWindowPos"), \
             patch("restore.win32gui.GetWindowRect", return_value=(999, 999, 1799, 1599)), \
             patch("restore.time.sleep"):
            restore._apply_placement(1, [100, 200, 800, 600], "normal")

        # Function completes without raising (logs error but doesn't crash)


class TestRestoreBrowserTabs:
    def test_opens_all_urls(self):
        import restore
        tabs = {
            "chrome": ["https://github.com", "https://example.com"],
            "edge": ["https://bing.com"],
        }
        with patch("restore._resolve_browser_exe", return_value=None), \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs)

        assert mock_open.call_count == 3
        mock_open.assert_any_call("https://github.com")
        mock_open.assert_any_call("https://example.com")
        mock_open.assert_any_call("https://bing.com")

    def test_handles_open_error_gracefully(self):
        import restore
        tabs = {"chrome": ["https://example.com"]}
        with patch("restore._resolve_browser_exe", return_value=None), \
             patch("restore.webbrowser.open", side_effect=Exception("error")):
            # Should not raise
            restore.restore_browser_tabs(tabs)

    def test_empty_tabs_no_calls(self):
        import restore
        with patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs({"chrome": [], "edge": []})
        mock_open.assert_not_called()

    def test_skips_non_web_urls(self):
        import restore
        tabs = {"chrome": ["https://example.com", "file:///c:/windows/system32/calc.exe"]}
        with patch("restore._resolve_browser_exe", return_value=None), \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs)
        mock_open.assert_called_once_with("https://example.com")


class TestFindBrowserExe:
    def test_returns_path_if_exists(self):
        import restore
        with patch("restore.os.path.isfile", return_value=True):
            result = restore._find_browser_exe("chrome")
        assert result is not None
        assert "chrome" in result.lower()

    def test_returns_none_if_not_found(self):
        import restore
        with patch("restore.os.path.isfile", return_value=False):
            result = restore._find_browser_exe("chrome")
        assert result is None

    def test_unknown_browser_returns_none(self):
        import restore
        result = restore._find_browser_exe("firefox")
        assert result is None


class TestFindRunningBrowserExe:
    def test_returns_matching_visible_browser_exe(self):
        import restore
        import win32con
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        pid_by_hwnd = {11: 501, 12: 502, 13: 503}
        path_by_pid = {
            501: r"C:\Program Files\Mozilla Firefox\firefox.exe",
            502: r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            503: r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        }

        def fake_enum(cb, extra):
            cb(11, None)
            cb(12, None)
            cb(13, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32process.GetWindowThreadProcessId", side_effect=lambda hwnd: (0, pid_by_hwnd[hwnd])), \
             patch("restore.win32api.OpenProcess", side_effect=lambda *_: f"handle-{_[2]}"), \
             patch("restore.win32process.GetModuleFileNameEx", side_effect=lambda handle, _: path_by_pid[int(handle.split('-')[-1])]), \
             patch("restore.win32api.CloseHandle"), \
             patch("restore._is_restorable_exe", return_value=True):
            result = restore._find_running_browser_exe("chrome")

        assert result == r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    def test_returns_none_when_no_visible_restorable_match(self):
        import restore
        import win32con
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        pid_by_hwnd = {21: 601, 22: 602}
        path_by_pid = {
            601: r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            602: r"C:\Program Files\Mozilla Firefox\firefox.exe",
        }

        def fake_enum(cb, extra):
            cb(21, None)
            cb(22, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", side_effect=lambda hwnd: hwnd == 22), \
             patch("restore.win32process.GetWindowThreadProcessId", side_effect=lambda hwnd: (0, pid_by_hwnd[hwnd])), \
             patch("restore.win32api.OpenProcess", side_effect=lambda *_: f"handle-{_[2]}"), \
             patch("restore.win32process.GetModuleFileNameEx", side_effect=lambda handle, _: path_by_pid[int(handle.split('-')[-1])]), \
             patch("restore.win32api.CloseHandle"), \
             patch("restore._is_restorable_exe", return_value=False):
            result = restore._find_running_browser_exe("chrome")

        assert result is None


class TestRestoreBrowserTabsWithExe:
    def test_prefers_saved_browser_hint_over_detected_exe(self):
        import restore
        tabs = {"chrome": ["https://github.com"]}
        hint_exe = r"C:\Hints\chrome.exe"
        detected_exe = r"C:\Detected\chrome.exe"

        with patch("restore._is_restorable_exe", side_effect=lambda path: path == hint_exe), \
             patch("restore._find_browser_exe", return_value=detected_exe), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_browser_tabs(tabs, {"chrome": hint_exe})

        mock_popen.assert_called_once_with([hint_exe, "https://github.com"])

    def test_routes_chrome_and_edge_urls_to_separate_executables(self):
        import restore
        tabs = {
            "chrome": ["https://github.com"],
            "edge": ["https://bing.com"],
        }
        hints = {
            "chrome": r"C:\Browsers\chrome.exe",
            "edge": r"C:\Browsers\msedge.exe",
        }

        with patch("restore._is_restorable_exe", return_value=True), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs, hints)

        mock_popen.assert_has_calls(
            [
                call([r"C:\Browsers\chrome.exe", "https://github.com"]),
                call([r"C:\Browsers\msedge.exe", "https://bing.com"]),
            ]
        )
        assert mock_popen.call_count == 2
        mock_open.assert_not_called()

    def test_uses_exe_when_found(self):
        import restore
        tabs = {"chrome": ["https://github.com"]}
        with patch("restore._resolve_browser_exe", return_value=r"C:\chrome.exe"), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_browser_tabs(tabs)
        mock_popen.assert_called_once_with([r"C:\chrome.exe", "https://github.com"])

    def test_falls_back_to_webbrowser_when_exe_not_found(self):
        import restore
        tabs = {"chrome": ["https://github.com"]}
        with patch("restore._resolve_browser_exe", return_value=None), \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs)
        mock_open.assert_called_once_with("https://github.com")

    def test_uses_running_browser_when_hint_and_detection_missing(self):
        import restore
        hint_exe = r"C:\Hints\chrome.exe"
        running_exe = r"C:\Running\chrome.exe"
        with patch("restore._is_restorable_exe", side_effect=lambda path: path == running_exe), \
             patch("restore._find_browser_exe", return_value=None), \
             patch("restore._find_running_browser_exe", return_value=running_exe):
            result = restore._resolve_browser_exe("chrome", {"chrome": hint_exe})
        assert result == running_exe

    def test_skips_empty_url_lists(self):
        import restore
        tabs = {"chrome": [], "edge": []}
        with patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs)
        mock_popen.assert_not_called()
        mock_open.assert_not_called()


    def _make_profile(self, exe=r"C:\Windows\notepad.exe"):
        return {
            "windows": [
                {"title": "Notepad", "exe": exe, "rect": [0, 0, 800, 600], "state": "normal"}
            ],
            "browser_tabs": {"chrome": ["https://example.com"], "edge": []},
        }

    def test_launches_exe_and_positions_window(self):
        import restore
        import win32con
        win32con.SW_SHOWNORMAL = 1
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        profile = self._make_profile()

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", return_value=99), \
             patch("restore.time.sleep"), \
             patch("restore._apply_placement") as mock_place, \
             patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        mock_popen.assert_called_once_with([r"C:\Windows\notepad.exe"])
        mock_place.assert_called_once_with(99, [0, 0, 800, 600], "normal")
        mock_tabs.assert_called_once_with(
            {"chrome": ["https://example.com"], "edge": []}, {}, skip_urls=set()
        )

    def test_passes_browser_exe_hints_to_tab_restore(self):
        import restore
        profile = {
            "windows": [],
            "browser_tabs": {"chrome": ["https://example.com"], "edge": []},
            "browser_exes": {"chrome": r"C:\Saved\chrome.exe", "edge": r"C:\Saved\msedge.exe"},
        }

        with patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        mock_tabs.assert_called_once_with(
            profile["browser_tabs"], profile["browser_exes"], skip_urls=set()
        )

    def test_ignores_profile_args_when_launching(self):
        import restore
        profile = self._make_profile()
        profile["windows"][0]["args"] = [r"C:\Windows\notepad.exe", "/p", "malicious.txt"]

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", return_value=99), \
             patch("restore.time.sleep"), \
             patch("restore._apply_placement"), \
             patch("restore.restore_browser_tabs"):
            restore.restore_profile(profile)

        mock_popen.assert_called_once_with([r"C:\Windows\notepad.exe"])

    def test_repositions_already_running_app(self):
        """If app is already open, reposition it without launching a new instance."""
        import restore
        import win32con
        win32con.SW_SHOWNORMAL = 1
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2

        profile = self._make_profile()

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[42]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._apply_placement") as mock_place, \
             patch("restore.restore_browser_tabs"):
            restore.restore_profile(profile)

        mock_popen.assert_not_called()
        mock_place.assert_called_once_with(42, [0, 0, 800, 600], "normal")

    def test_launches_additional_instance_when_saved_windows_exceed_running(self):
        import restore

        profile = {
            "windows": [
                {"title": "Edge A", "exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "rect": [0, 0, 800, 600], "state": "normal", "hwnd": 42},
                {"title": "Edge B", "exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "rect": [900, 0, 800, 600], "state": "normal", "hwnd": 99},
            ],
            "browser_tabs": {},
        }

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", side_effect=[[42], [42]]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", return_value=99) as mock_wait, \
             patch("restore.time.sleep"), \
             patch("restore._apply_placement") as mock_place:
            restore.restore_profile(profile)

        # Second entry: existing=[42] (browser running, all assigned) → relay command, NO debug port
        mock_popen.assert_called_once_with([
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ])
        mock_wait.assert_called_once_with(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", {42})
        assert mock_place.call_count == 2
        mock_place.assert_any_call(42, [0, 0, 800, 600], "normal")
        mock_place.assert_any_call(99, [900, 0, 800, 600], "normal")

    def test_skips_missing_exe(self):
        import restore
        profile = self._make_profile(exe=r"C:\nonexistent\app.exe")

        with patch("restore.os.path.isfile", return_value=False), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_profile(profile)

        mock_popen.assert_not_called()

    def test_skips_non_exe_path(self):
        import restore
        profile = self._make_profile(exe=r"C:\temp\app.bat")
        profile["browser_tabs"] = {}

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_profile(profile)

        mock_popen.assert_not_called()

    def test_handles_launch_failure(self):
        import restore
        profile = self._make_profile()

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[]), \
             patch("restore.subprocess.Popen", side_effect=Exception("launch failed")), \
             patch("restore._apply_placement") as mock_place:
            restore.restore_profile(profile)

        mock_place.assert_not_called()

    def test_handles_window_timeout(self):
        import restore
        profile = self._make_profile()

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[]), \
             patch("restore.subprocess.Popen"), \
             patch("restore._wait_for_window", return_value=None), \
             patch("restore._apply_placement") as mock_place:
            restore.restore_profile(profile)

        mock_place.assert_not_called()


class TestRestoreBrowserTabsSkipUrls:
    def test_skip_urls_prevents_duplicate_open(self):
        import restore
        tabs = {"edge": ["https://ekstrabladet.dk/", "https://www.bt.dk/"]}
        with patch("restore._resolve_browser_exe", return_value=r"C:\msedge.exe"), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_browser_tabs(tabs, skip_urls={"https://ekstrabladet.dk/"})
        # Only bt.dk opened; ekstrabladet.dk skipped
        mock_popen.assert_called_once_with([r"C:\msedge.exe", "https://www.bt.dk/"])

    def test_skip_urls_none_opens_all(self):
        import restore
        tabs = {"edge": ["https://ekstrabladet.dk/", "https://www.bt.dk/"]}
        with patch("restore._resolve_browser_exe", return_value=r"C:\msedge.exe"), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_browser_tabs(tabs, skip_urls=None)
        assert mock_popen.call_count == 2

    def test_skip_all_urls_skips_browser(self):
        import restore
        tabs = {"edge": ["https://bt.dk/"]}
        with patch("restore._resolve_browser_exe", return_value=r"C:\msedge.exe"), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_browser_tabs(tabs, skip_urls={"https://bt.dk/"})
        mock_popen.assert_not_called()


class TestRestoreProfilePerWindowUrl:
    def test_browser_window_with_url_uses_new_window_flag(self):
        """Browser window entries with a 'url' field launch with --new-window."""
        import restore
        profile = {
            "windows": [
                {
                    "title": "Ekstra Bladet - Microsoft Edge",
                    "exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    "rect": [0, 0, 1280, 720],
                    "state": "normal",
                    "url": "https://ekstrabladet.dk/",
                }
            ],
            "browser_tabs": {"edge": ["https://ekstrabladet.dk/"]},
            "browser_exes": {},
        }

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", return_value=11), \
             patch("restore.time.sleep"), \
             patch("restore._apply_placement"), \
             patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        mock_popen.assert_called_once_with([
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "--new-window",
            "https://ekstrabladet.dk/",
            "--remote-debugging-port=9223",
            "--remote-debugging-address=127.0.0.1",
        ])
        # URL already opened via window; restore_browser_tabs must skip it
        mock_tabs.assert_called_once_with(
            {"edge": ["https://ekstrabladet.dk/"]}, {}, skip_urls={"https://ekstrabladet.dk/"}
        )

    def test_two_browser_windows_each_get_new_window(self):
        """Two separate browser window entries each launch with --new-window <url>."""
        import restore
        edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        profile = {
            "windows": [
                {"title": "Ekstra Bladet - Edge", "exe": edge_exe, "rect": [0, 0, 800, 600], "state": "normal", "url": "https://ekstrabladet.dk/"},
                {"title": "B.T. - Edge", "exe": edge_exe, "rect": [900, 0, 800, 600], "state": "normal", "url": "https://www.bt.dk/"},
            ],
            "browser_tabs": {"edge": ["https://ekstrabladet.dk/", "https://www.bt.dk/"]},
            "browser_exes": {},
        }

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", side_effect=[[], [11]]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", side_effect=[11, 12]), \
             patch("restore.time.sleep"), \
             patch("restore._apply_placement"), \
             patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        assert mock_popen.call_count == 2
        # First window: fresh start (no existing) → includes debug port
        mock_popen.assert_any_call([edge_exe, "--new-window", "https://ekstrabladet.dk/", "--remote-debugging-port=9223", "--remote-debugging-address=127.0.0.1"])
        # Second window: browser already running (relay) → no debug port flag
        mock_popen.assert_any_call([edge_exe, "--new-window", "https://www.bt.dk/"])
        # Both URLs in skip set
        args, kwargs = mock_tabs.call_args
        assert kwargs["skip_urls"] == {"https://ekstrabladet.dk/", "https://www.bt.dk/"}

    def test_browser_window_without_url_launches_plain(self):
        """Old profile entries without 'url' still launch without --new-window."""
        import restore
        profile = {
            "windows": [
                {"title": "Edge", "exe": r"C:\msedge.exe", "rect": [0, 0, 800, 600], "state": "normal"},
            ],
            "browser_tabs": {"edge": ["https://bt.dk/"]},
            "browser_exes": {},
        }

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", return_value=11), \
             patch("restore.time.sleep"), \
             patch("restore._apply_placement"), \
             patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        mock_popen.assert_called_once_with([
            r"C:\msedge.exe",
            "--remote-debugging-port=9223",
            "--remote-debugging-address=127.0.0.1",
        ])
        mock_tabs.assert_called_once_with({"edge": ["https://bt.dk/"]}, {}, skip_urls=set())

    def test_already_running_browser_window_url_is_skipped(self):
        """When repositioning an already-open browser window, its URL goes into skip set."""
        import restore
        edge_exe = r"C:\msedge.exe"
        profile = {
            "windows": [
                {"title": "Edge", "exe": edge_exe, "rect": [0, 0, 800, 600], "state": "normal", "url": "https://bt.dk/"},
            ],
            "browser_tabs": {"edge": ["https://bt.dk/"]},
            "browser_exes": {},
        }

        with patch("restore.os.path.isfile", return_value=True), \
             patch("restore._find_windows_by_exe", return_value=[42]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._apply_placement"), \
             patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        mock_popen.assert_not_called()
        mock_tabs.assert_called_once_with(
            {"edge": ["https://bt.dk/"]}, {}, skip_urls={"https://bt.dk/"}
        )
