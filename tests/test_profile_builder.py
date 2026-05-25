"""Tests for profile_builder.py profile payload assembly."""

from unittest.mock import patch


class TestBuildProfilePayload:
    def test_includes_windows_tabs_and_executable_hints(self):
        import profile_builder

        cfg = {"chrome_debug_port": 19222, "edge_debug_port": 19223}
        windows = [{"title": "Editor", "exe": r"C:\Tools\editor.exe"}]
        tabs_with_titles = {
            "chrome": [{"title": "Example", "url": "https://example.com"}],
            "edge": [{"title": "GitHub", "url": "https://github.com"}],
        }
        with patch("profile_builder.capture.capture_windows", return_value=windows), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value=tabs_with_titles) as mock_tabs, \
             patch("profile_builder.browser_runtime.find_browser_exe", side_effect=[r"C:\Chrome\chrome.exe", r"C:\Edge\msedge.exe"]):
            payload = profile_builder.build_profile_payload(cfg)

        assert payload["windows"] == windows
        assert payload["browser_tabs"] == {
            "chrome": ["https://example.com"],
            "edge": ["https://github.com"],
        }
        assert payload["browser_exes"] == {
            "chrome": r"C:\Chrome\chrome.exe",
            "edge": r"C:\Edge\msedge.exe",
        }
        mock_tabs.assert_called_once_with(chrome_port=19222, edge_port=19223)

    def test_uses_default_ports_and_omits_missing_hints(self):
        import profile_builder

        with patch("profile_builder.capture.capture_windows", return_value=[]), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value={"chrome": [], "edge": []}) as mock_tabs, \
             patch("profile_builder.browser_runtime.find_browser_exe", side_effect=[None, r"C:\Edge\msedge.exe"]):
            payload = profile_builder.build_profile_payload({})

        assert payload["windows"] == []
        assert payload["browser_tabs"] == {"chrome": [], "edge": []}
        assert payload["browser_exes"] == {"edge": r"C:\Edge\msedge.exe"}
        mock_tabs.assert_called_once_with(chrome_port=9222, edge_port=9223)

    def test_annotates_browser_window_with_matching_url(self):
        """Browser windows get a 'url' field when a CDP tab title matches the window title."""
        import profile_builder

        windows = [
            {"title": "Ekstra Bladet - Personal - Microsoft Edge", "exe": r"C:\msedge.exe"},
            {"title": "Notepad", "exe": r"C:\Windows\notepad.exe"},
        ]
        tabs_with_titles = {
            "chrome": [],
            "edge": [{"title": "Ekstra Bladet", "url": "https://ekstrabladet.dk/"}],
        }

        with patch("profile_builder.capture.capture_windows", return_value=windows), \
             patch("profile_builder.browser.capture_browser_tabs_with_titles", return_value=tabs_with_titles), \
             patch("profile_builder.browser_runtime.find_browser_exe", return_value=None), \
             patch("profile_builder.browser.match_tab_url_by_title", side_effect=lambda title, tabs: "https://ekstrabladet.dk/" if "Ekstra" in title else None) as mock_match:
            payload = profile_builder.build_profile_payload({})

        # Edge window should have url annotated; notepad should not
        edge_entry = payload["windows"][0]
        notepad_entry = payload["windows"][1]
        assert edge_entry.get("url") == "https://ekstrabladet.dk/"
        assert "url" not in notepad_entry
