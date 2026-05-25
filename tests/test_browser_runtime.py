"""Tests for browser_runtime.py helpers."""

from unittest.mock import MagicMock, call, patch


class TestFindBrowserExe:
    def test_returns_first_edge_candidate(self):
        import browser_runtime

        candidates = {
            "edge": [
                r"C:\Missing\msedge.exe",
                r"C:\Present\msedge.exe",
                r"C:\AlsoPresent\msedge.exe",
            ]
        }
        with patch("browser_runtime._BROWSER_EXES", candidates), \
             patch("browser_runtime.os.path.isfile", side_effect=lambda path: "Present" in path):
            result = browser_runtime.find_browser_exe("edge")

        assert result == r"C:\Present\msedge.exe"
        assert result.lower().endswith("msedge.exe")


class TestLaunchBrowserCaptureMode:
    def test_calls_subprocess_with_capture_flags(self):
        import browser_runtime

        proc = MagicMock()
        with patch("browser_runtime.find_browser_exe", return_value=r"C:\Edge\msedge.exe"), \
             patch("browser_runtime.subprocess.Popen", return_value=proc) as mock_popen:
            result = browser_runtime.launch_browser_capture_mode("edge", 9223)

        assert result is proc
        mock_popen.assert_called_once_with(
            [
                r"C:\Edge\msedge.exe",
                "--remote-debugging-port=9223",
                "--remote-debugging-address=127.0.0.1",
            ]
        )


class TestGetCaptureStatus:
    def test_combines_probe_results_and_tab_counts(self):
        import browser_runtime

        tabs = {"chrome": ["https://a", "https://b"], "edge": ["https://c"]}
        with patch("browser_runtime._probe_port", side_effect=[True, False]) as mock_probe, \
             patch("browser_runtime.browser.capture_browser_tabs", return_value=tabs) as mock_capture:
            result = browser_runtime.get_capture_status(chrome_port=9222, edge_port=9223)

        mock_capture.assert_called_once_with(chrome_port=9222, edge_port=9223)
        mock_probe.assert_has_calls([call(9222), call(9223)])
        assert result == {
            "chrome": {"connected": True, "count": 2},
            "edge": {"connected": False, "count": 1},
        }
