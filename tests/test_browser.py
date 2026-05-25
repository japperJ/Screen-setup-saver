"""Tests for browser.py — CDP tab capture."""

import json
from unittest.mock import MagicMock, patch
import pytest


class TestFetchTabs:
    def test_returns_list_on_success(self):
        import browser
        fake_data = [{"type": "page", "url": "https://example.com"}]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("browser.urllib.request.urlopen", return_value=mock_resp):
            result = browser._fetch_tabs(9222)

        assert result == fake_data

    def test_returns_empty_on_connection_error(self):
        import browser
        with patch("browser.urllib.request.urlopen", side_effect=OSError("refused")):
            result = browser._fetch_tabs(9222)
        assert result == []

    def test_returns_empty_on_timeout(self):
        import browser
        import urllib.error
        with patch("browser.urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = browser._fetch_tabs(9222)
        assert result == []

    def test_returns_empty_if_response_not_list(self):
        import browser
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"error": "not a list"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("browser.urllib.request.urlopen", return_value=mock_resp):
            result = browser._fetch_tabs(9222)
        assert result == []


class TestExtractPageTabs:
    def test_filters_to_page_type(self):
        import browser
        raw = [
            {"type": "page", "url": "https://example.com"},
            {"type": "background_page", "url": "https://extension.com"},
            {"type": "page", "url": "https://github.com"},
        ]
        assert browser._extract_page_tabs(raw) == ["https://example.com", "https://github.com"]

    def test_skips_chrome_internal_urls(self):
        import browser
        raw = [
            {"type": "page", "url": "chrome://newtab/"},
            {"type": "page", "url": "chrome://settings/"},
            {"type": "page", "url": "https://google.com"},
        ]
        assert browser._extract_page_tabs(raw) == ["https://google.com"]

    def test_skips_edge_internal_urls(self):
        import browser
        raw = [
            {"type": "page", "url": "edge://newtab/"},
            {"type": "page", "url": "https://bing.com"},
        ]
        assert browser._extract_page_tabs(raw) == ["https://bing.com"]

    def test_skips_chrome_extensions(self):
        import browser
        raw = [
            {"type": "page", "url": "chrome-extension://abc/popup.html"},
            {"type": "page", "url": "https://example.com"},
        ]
        assert browser._extract_page_tabs(raw) == ["https://example.com"]

    def test_keeps_only_http_https_urls(self):
        import browser
        raw = [
            {"type": "page", "url": "https://example.com"},
            {"type": "page", "url": "file:///C:/Users/name/index.html"},
            {"type": "page", "url": "ftp://example.com/file.txt"},
        ]
        assert browser._extract_page_tabs(raw) == ["https://example.com"]

    def test_skips_about_urls(self):
        import browser
        raw = [{"type": "page", "url": "about:blank"}]
        assert browser._extract_page_tabs(raw) == []

    def test_skips_empty_url(self):
        import browser
        raw = [{"type": "page", "url": ""}]
        assert browser._extract_page_tabs(raw) == []

    def test_empty_input(self):
        import browser
        assert browser._extract_page_tabs([]) == []


class TestCaptureBrowserTabs:
    def test_returns_chrome_and_edge_keys(self):
        import browser
        with patch("browser._fetch_tabs", return_value=[]):
            result = browser.capture_browser_tabs()
        assert "chrome" in result
        assert "edge" in result

    def test_uses_correct_ports(self):
        import browser
        calls = []

        def fake_fetch(port):
            calls.append(port)
            return []

        with patch("browser._fetch_tabs", side_effect=fake_fetch):
            browser.capture_browser_tabs(chrome_port=9222, edge_port=9223)

        assert 9222 in calls
        assert 9223 in calls

    def test_both_browsers_not_running(self):
        import browser
        with patch("browser._fetch_tabs", return_value=[]):
            result = browser.capture_browser_tabs()
        assert result == {"chrome": [], "edge": []}

    def test_custom_ports(self):
        import browser
        calls = []

        def fake_fetch(port):
            calls.append(port)
            return []

        with patch("browser._fetch_tabs", side_effect=fake_fetch):
            browser.capture_browser_tabs(chrome_port=19222, edge_port=19223)

        assert calls == [19222, 19223]


class TestExtractPageTabsWithTitles:
    def test_returns_title_and_url(self):
        import browser
        raw = [{"type": "page", "url": "https://example.com", "title": "Example"}]
        result = browser._extract_page_tabs_with_titles(raw)
        assert result == [{"title": "Example", "url": "https://example.com"}]

    def test_skips_non_page_types(self):
        import browser
        raw = [
            {"type": "background_page", "url": "https://ext.com", "title": "Extension"},
            {"type": "page", "url": "https://example.com", "title": "Example"},
        ]
        result = browser._extract_page_tabs_with_titles(raw)
        assert result == [{"title": "Example", "url": "https://example.com"}]

    def test_skips_non_http_urls(self):
        import browser
        raw = [
            {"type": "page", "url": "file:///index.html", "title": "File"},
            {"type": "page", "url": "https://example.com", "title": "Example"},
        ]
        result = browser._extract_page_tabs_with_titles(raw)
        assert result == [{"title": "Example", "url": "https://example.com"}]

    def test_skips_tabs_with_empty_title(self):
        import browser
        raw = [{"type": "page", "url": "https://example.com", "title": ""}]
        result = browser._extract_page_tabs_with_titles(raw)
        assert result == []

    def test_empty_input(self):
        import browser
        assert browser._extract_page_tabs_with_titles([]) == []


class TestMatchTabUrlByTitle:
    def test_matches_window_starting_with_tab_title(self):
        import browser
        tabs = [{"title": "Ekstra Bladet", "url": "https://ekstrabladet.dk/"}]
        result = browser.match_tab_url_by_title(
            "Ekstra Bladet - Personal - Microsoft Edge", tabs
        )
        assert result == "https://ekstrabladet.dk/"

    def test_case_insensitive_match(self):
        import browser
        tabs = [{"title": "EKSTRA BLADET", "url": "https://ekstrabladet.dk/"}]
        result = browser.match_tab_url_by_title(
            "Ekstra Bladet - Personal - Microsoft Edge", tabs
        )
        assert result == "https://ekstrabladet.dk/"

    def test_returns_longest_match(self):
        import browser
        tabs = [
            {"title": "Ek", "url": "https://short.com/"},
            {"title": "Ekstra Bladet", "url": "https://ekstrabladet.dk/"},
        ]
        result = browser.match_tab_url_by_title(
            "Ekstra Bladet - Personal - Microsoft Edge", tabs
        )
        assert result == "https://ekstrabladet.dk/"

    def test_returns_none_when_no_match(self):
        import browser
        tabs = [{"title": "B.T.", "url": "https://bt.dk/"}]
        result = browser.match_tab_url_by_title(
            "Ekstra Bladet - Personal - Microsoft Edge", tabs
        )
        assert result is None

    def test_returns_none_for_empty_tabs(self):
        import browser
        assert browser.match_tab_url_by_title("Some Window", []) is None

    def test_skips_tabs_with_empty_title(self):
        import browser
        tabs = [{"title": "", "url": "https://example.com"}]
        result = browser.match_tab_url_by_title("Some Window - Edge", tabs)
        assert result is None


class TestCaptureBrowserTabsWithTitles:
    def test_returns_chrome_and_edge_keys(self):
        import browser
        with patch("browser._fetch_tabs", return_value=[]):
            result = browser.capture_browser_tabs_with_titles()
        assert "chrome" in result
        assert "edge" in result

    def test_returns_title_and_url_dicts(self):
        import browser
        raw = [{"type": "page", "url": "https://example.com", "title": "Example"}]
        with patch("browser._fetch_tabs", return_value=raw):
            result = browser.capture_browser_tabs_with_titles()
        assert result["chrome"] == [{"title": "Example", "url": "https://example.com"}]
        assert result["edge"] == [{"title": "Example", "url": "https://example.com"}]

    def test_uses_correct_ports(self):
        import browser
        calls = []

        def fake_fetch(port):
            calls.append(port)
            return []

        with patch("browser._fetch_tabs", side_effect=fake_fetch):
            browser.capture_browser_tabs_with_titles(chrome_port=9222, edge_port=9223)

        assert 9222 in calls
        assert 9223 in calls
