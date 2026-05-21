"""Tests for capture.py — window enumeration and metadata extraction."""

import sys
from unittest.mock import MagicMock, patch, call
import pytest

# conftest.py already stubs win32gui, win32process, win32con, win32api


class TestIsCapturable:
    """Unit tests for the _is_capturable filter."""

    def _call(self, hwnd=1, visible=True, title="My App", ex_style=0, cls="Chrome_WidgetWin_1"):
        import capture
        import win32con
        win32con.GWL_EXSTYLE = -20
        win32con.WS_EX_TOOLWINDOW = 0x80
        with patch.multiple(
            "capture.win32gui",
            IsWindowVisible=MagicMock(return_value=visible),
            GetWindowText=MagicMock(return_value=title),
            GetWindowLong=MagicMock(return_value=ex_style),
            GetClassName=MagicMock(return_value=cls),
        ):
            return capture._is_capturable(hwnd)

    def test_normal_window_passes(self):
        assert self._call() is True

    def test_invisible_rejected(self):
        assert self._call(visible=False) is False

    def test_empty_title_rejected(self):
        assert self._call(title="   ") is False

    def test_tool_window_rejected(self):
        import capture
        import win32con
        win32con.WS_EX_TOOLWINDOW = 0x80
        assert self._call(ex_style=0x80) is False

    def test_skip_class_rejected(self):
        assert self._call(cls="Shell_TrayWnd") is False

    def test_progman_rejected(self):
        assert self._call(cls="Progman") is False


class TestGetWindowState:
    def _call(self, show_cmd):
        import capture
        import win32con
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2
        placement = (0, show_cmd, 0, (0,0,0,0), (0,0,800,600))
        with patch("capture.win32gui.GetWindowPlacement", return_value=placement):
            return capture._get_window_state(1)

    def test_normal(self):
        assert self._call(1) == "normal"

    def test_maximized(self):
        import win32con
        win32con.SW_SHOWMAXIMIZED = 3
        assert self._call(3) == "maximized"

    def test_minimized(self):
        import win32con
        win32con.SW_SHOWMINIMIZED = 2
        assert self._call(2) == "minimized"


class TestGetRect:
    def test_computes_width_height(self):
        import capture
        # restore rect: left=100, top=200, right=900, bottom=800
        placement = (0, 1, 0, (0,0,0,0), (100, 200, 900, 800))
        with patch("capture.win32gui.GetWindowPlacement", return_value=placement):
            rect = capture._get_rect(1)
        assert rect == [100, 200, 800, 600]


class TestGetCmdline:
    def test_returns_cmdline(self):
        import capture
        import win32con
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        with patch("capture.win32process.GetWindowThreadProcessId", return_value=(0, 123)), \
             patch("capture.psutil.Process") as mock_proc:
            mock_proc.return_value.cmdline.return_value = [r"C:\chrome.exe", "--remote-debugging-port=9222"]
            result = capture._get_cmdline(1)
        assert result == [r"C:\chrome.exe", "--remote-debugging-port=9222"]

    def test_returns_empty_on_error(self):
        import capture
        with patch("capture.win32process.GetWindowThreadProcessId", side_effect=Exception("error")):
            result = capture._get_cmdline(1)
        assert result == []


    def test_returns_list_of_dicts(self):
        import capture
        import win32con
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2
        win32con.WS_EX_TOOLWINDOW = 0x80
        win32con.GWL_EXSTYLE = -20
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        placement = (0, 1, 0, (0,0,0,0), (0, 0, 800, 600))

        def fake_enum(cb, extra):
            cb(1, None)  # one window
            cb(2, None)  # second window
            return True

        with patch("capture.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("capture.win32gui.IsWindowVisible", return_value=True), \
             patch("capture.win32gui.GetWindowText", return_value="Notepad"), \
             patch("capture.win32gui.GetWindowLong", return_value=0), \
             patch("capture.win32gui.GetClassName", return_value="Notepad"), \
             patch("capture.win32gui.GetWindowPlacement", return_value=placement), \
             patch("capture.win32process.GetWindowThreadProcessId", return_value=(0, 123)), \
             patch("capture.win32api.OpenProcess", return_value=MagicMock()), \
             patch("capture.win32process.GetModuleFileNameEx", return_value=r"C:\Windows\notepad.exe"), \
             patch("capture.win32api.CloseHandle"):
            result = capture.capture_windows()

        assert len(result) == 2
        w = result[0]
        assert w["title"] == "Notepad"
        assert w["exe"] == r"C:\Windows\notepad.exe"
        assert w["rect"] == [0, 0, 800, 600]
        assert w["state"] == "normal"
        assert "hwnd" in w

    def test_filters_invisible_windows(self):
        import capture

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("capture.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("capture.win32gui.IsWindowVisible", return_value=False):
            result = capture.capture_windows()

        assert result == []

    def test_exe_error_returns_empty_string(self):
        """If OpenProcess fails, exe should be empty string, not crash."""
        import capture
        import win32con
        win32con.SW_SHOWMAXIMIZED = 3
        win32con.SW_SHOWMINIMIZED = 2
        win32con.WS_EX_TOOLWINDOW = 0x80
        win32con.GWL_EXSTYLE = -20
        win32con.PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        placement = (0, 1, 0, (0,0,0,0), (0, 0, 800, 600))

        def fake_enum(cb, extra):
            cb(1, None)
            return True

        with patch("capture.win32gui.EnumWindows", side_effect=fake_enum), \
             patch("capture.win32gui.IsWindowVisible", return_value=True), \
             patch("capture.win32gui.GetWindowText", return_value="App"), \
             patch("capture.win32gui.GetWindowLong", return_value=0), \
             patch("capture.win32gui.GetClassName", return_value="AppClass"), \
             patch("capture.win32gui.GetWindowPlacement", return_value=placement), \
             patch("capture.win32process.GetWindowThreadProcessId", side_effect=Exception("access denied")):
            result = capture.capture_windows()

        assert result[0]["exe"] == ""
