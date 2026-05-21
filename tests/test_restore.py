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

    def test_handles_access_error_gracefully(self):
        import restore

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("restore.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("restore.win32gui.IsWindowVisible", return_value=True), \
             patch("restore.win32process.GetWindowThreadProcessId", side_effect=Exception("access denied")):
            result = restore._find_windows_by_exe(r"C:\notepad.exe")
        assert result == []


class TestApplyPlacement:
    def test_normal_state(self):
        import restore
        import win32con
        win32con.SW_SHOWNORMAL = 1
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2

        with patch("restore.win32gui.SetWindowPlacement") as mock_place:
            restore._apply_placement(1, [100, 200, 800, 600], "normal")

        mock_place.assert_called_once()
        args = mock_place.call_args[0]
        placement = args[1]
        assert placement[1] == win32con.SW_SHOWNORMAL
        assert placement[4] == (100, 200, 900, 800)  # right=100+800, bottom=200+600

    def test_maximized_state(self):
        import restore
        import win32con
        win32con.SW_SHOWNORMAL = 1
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2

        with patch("restore.win32gui.SetWindowPlacement") as mock_place:
            restore._apply_placement(1, [0, 0, 1920, 1080], "maximized")

        placement = mock_place.call_args[0][1]
        assert placement[1] == win32con.SW_SHOWMAXIMIZED

    def test_retries_on_failure(self):
        import restore
        import win32con
        win32con.SW_SHOWNORMAL = 1
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2

        with patch("restore.win32gui.SetWindowPlacement", side_effect=Exception("error")), \
             patch("restore.time.sleep") as mock_sleep:
            restore._apply_placement(1, [0, 0, 800, 600], "normal")

        # Should have slept between retries
        assert mock_sleep.call_count == restore._PLACE_RETRIES - 1


class TestRestoreBrowserTabs:
    def test_opens_all_urls(self):
        import restore
        tabs = {
            "chrome": ["https://github.com", "https://example.com"],
            "edge": ["https://bing.com"],
        }
        with patch("restore._find_browser_exe", return_value=None), \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs)

        assert mock_open.call_count == 3
        mock_open.assert_any_call("https://github.com")
        mock_open.assert_any_call("https://example.com")
        mock_open.assert_any_call("https://bing.com")

    def test_handles_open_error_gracefully(self):
        import restore
        tabs = {"chrome": ["https://example.com"]}
        with patch("restore._find_browser_exe", return_value=None), \
             patch("restore.webbrowser.open", side_effect=Exception("error")):
            # Should not raise
            restore.restore_browser_tabs(tabs)

    def test_empty_tabs_no_calls(self):
        import restore
        with patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs({"chrome": [], "edge": []})
        mock_open.assert_not_called()


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


class TestRestoreBrowserTabsWithExe:
    def test_uses_exe_when_found(self):
        import restore
        tabs = {"chrome": ["https://github.com"]}
        with patch("restore._find_browser_exe", return_value=r"C:\chrome.exe"), \
             patch("restore.subprocess.Popen") as mock_popen:
            restore.restore_browser_tabs(tabs)
        mock_popen.assert_called_once_with([r"C:\chrome.exe", "https://github.com"])

    def test_falls_back_to_webbrowser_when_exe_not_found(self):
        import restore
        tabs = {"chrome": ["https://github.com"]}
        with patch("restore._find_browser_exe", return_value=None), \
             patch("restore.webbrowser.open") as mock_open:
            restore.restore_browser_tabs(tabs)
        mock_open.assert_called_once_with("https://github.com")

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
             patch("restore._find_windows_by_exe", side_effect=[set(), [99]]), \
             patch("restore.subprocess.Popen") as mock_popen, \
             patch("restore._wait_for_window", return_value=99), \
             patch("restore._apply_placement") as mock_place, \
             patch("restore.restore_browser_tabs") as mock_tabs:
            restore.restore_profile(profile)

        mock_popen.assert_called_once()
        mock_place.assert_called_once_with(99, [0, 0, 800, 600], "normal")
        mock_tabs.assert_called_once_with({"chrome": ["https://example.com"], "edge": []})

    def test_skips_missing_exe(self):
        import restore
        profile = self._make_profile(exe=r"C:\nonexistent\app.exe")

        with patch("restore.os.path.isfile", return_value=False), \
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
