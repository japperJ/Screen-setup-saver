"""Tests for settings_ui startup preference integration."""

from unittest.mock import Mock, patch


class TestProfileDetailsFormatting:
    def test_formats_windows_and_browser_urls(self):
        import settings_ui

        profile = {
            "windows": [
                {"title": "Docs - Edge", "exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"},
                {"title": "Notepad", "exe": r"C:\Windows\System32\notepad.exe"},
            ],
            "browser_tabs": {
                "chrome": ["https://example.com"],
                "edge": ["https://github.com", "https://bing.com"],
            },
        }
        text = settings_ui._format_profile_details(profile)

        assert "Windows captured: 2" in text
        assert "Browser tabs captured: 3" in text
        assert "https://github.com" in text
        assert "https://bing.com" in text
        assert "Apps:" in text
        assert "msedge.exe" in text
        assert "notepad.exe" in text

    def test_formats_empty_profile(self):
        import settings_ui

        text = settings_ui._format_profile_details({"windows": [], "browser_tabs": {"chrome": [], "edge": []}})

        assert "Windows captured: 0" in text
        assert "Browser tabs captured: 0" in text
        assert "No browser URLs saved in this profile." in text
        assert "Launch browsers in Capture Mode before saving." in text


class TestStartupPreference:
    def test_enable_calls_startup_and_saves_config(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)

        cfg = {"hotkey_save": "ctrl+alt+s", "start_with_windows": False}
        with patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.prof.save_config") as mock_save, \
             patch("settings_ui.startup.enable_startup") as mock_enable, \
             patch("settings_ui.startup.disable_startup") as mock_disable:
            win._set_startup_preference(True)

        mock_enable.assert_called_once_with()
        mock_disable.assert_not_called()
        assert cfg["start_with_windows"] is True
        mock_save.assert_called_once_with(cfg)

    def test_disable_calls_startup_and_saves_config(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)

        cfg = {"hotkey_save": "ctrl+alt+s", "start_with_windows": True}
        with patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.prof.save_config") as mock_save, \
             patch("settings_ui.startup.enable_startup") as mock_enable, \
             patch("settings_ui.startup.disable_startup") as mock_disable:
            win._set_startup_preference(False)

        mock_enable.assert_not_called()
        mock_disable.assert_called_once_with()
        assert cfg["start_with_windows"] is False
        mock_save.assert_called_once_with(cfg)


class TestSaveLayout:
    def test_save_layout_updates_last_profile_in_config(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._on_save = Mock()
        win._refresh_profiles = Mock()

        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": [], "browser_tabs": {"chrome": ["https://example.com"], "edge": []}, "browser_exes": {}}
        with patch("settings_ui.simpledialog.askstring", return_value="  Work  "), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload) as mock_build, \
             patch("settings_ui.prof.save_profile") as mock_save_profile, \
             patch("settings_ui.prof.save_config") as mock_save_config, \
             patch("settings_ui.messagebox.showinfo") as mock_info:
            win._save_layout()

        mock_build.assert_called_once_with(cfg)
        mock_save_profile.assert_called_once_with("Work", payload)
        assert cfg["last_profile"] == "Work"
        mock_save_config.assert_called_once_with(cfg)
        win._on_save.assert_called_once_with(cfg)
        win._refresh_profiles.assert_called_once_with()
        mock_info.assert_called_once()

    def test_save_layout_keeps_success_when_on_save_callback_fails(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._on_save = Mock(side_effect=RuntimeError("callback boom"))
        win._refresh_profiles = Mock()

        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": [], "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile") as mock_save_profile, \
             patch("settings_ui.prof.save_config") as mock_save_config, \
             patch("settings_ui.messagebox.showwarning") as mock_warning, \
             patch("settings_ui.messagebox.showerror") as mock_error:
            win._save_layout()

        mock_save_profile.assert_called_once_with("Work", payload)
        assert cfg["last_profile"] == "Work"
        mock_save_config.assert_called_once_with(cfg)
        win._on_save.assert_called_once_with(cfg)
        win._refresh_profiles.assert_called_once_with()
        mock_warning.assert_called_once()
        mock_error.assert_not_called()

    def test_save_layout_warns_when_no_browser_tabs_captured(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._on_save = Mock()
        win._refresh_profiles = Mock()

        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": [], "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile") as mock_save_profile, \
             patch("settings_ui.prof.save_config") as mock_save_config, \
             patch("settings_ui.messagebox.showwarning") as mock_warning, \
             patch("settings_ui.messagebox.showinfo") as mock_info:
            win._save_layout()

        mock_save_profile.assert_called_once_with("Work", payload)
        assert cfg["last_profile"] == "Work"
        mock_save_config.assert_called_once_with(cfg)
        win._on_save.assert_called_once_with(cfg)
        win._refresh_profiles.assert_called_once_with()
        mock_warning.assert_called_once_with(
            "Saved without browser URLs",
            "No browser tabs captured. Launch browsers in Capture Mode before saving.",
            parent=win._win,
        )
        mock_info.assert_not_called()

    def test_save_layout_warns_when_config_save_fails_after_profile_save(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._on_save = Mock()
        win._refresh_profiles = Mock()

        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": [], "browser_tabs": {"chrome": ["https://example.com"], "edge": []}, "browser_exes": {}}
        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile") as mock_save_profile, \
             patch("settings_ui.prof.save_config", side_effect=RuntimeError("config write failed")) as mock_save_config, \
             patch("settings_ui.messagebox.showwarning") as mock_warning, \
             patch("settings_ui.messagebox.showerror") as mock_error:
            win._save_layout()

        mock_save_profile.assert_called_once_with("Work", payload)
        mock_save_config.assert_called_once_with(cfg)
        win._on_save.assert_not_called()
        win._refresh_profiles.assert_called_once_with()
        mock_warning.assert_called_once_with(
            "Saved with warning",
            "Profile 'Work' saved, but updating defaults failed: config write failed",
            parent=win._win,
        )
        mock_error.assert_not_called()


class TestBrowserSetup:
    def test_test_browser_capture_shows_connected_and_url_counts(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._chrome_port_var = Mock(get=Mock(return_value="9222"))
        win._edge_port_var = Mock(get=Mock(return_value="9223"))

        status = {
            "chrome": {"connected": True, "count": 2},
            "edge": {"connected": False, "count": 1},
        }
        with patch("settings_ui.browser_runtime.get_capture_status", return_value=status) as mock_status, \
             patch("settings_ui.messagebox.showinfo") as mock_info:
            win._test_browser_capture()

        mock_status.assert_called_once_with(9222, 9223)
        mock_info.assert_called_once()
        title, msg = mock_info.call_args.args[:2]
        assert title == "Browser capture status"
        assert "Chrome: Connected, URLs=2" in msg
        assert "Edge: Not connected, URLs=1" in msg

    def test_test_browser_capture_handles_malformed_counts(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._chrome_port_var = Mock(get=Mock(return_value="9222"))
        win._edge_port_var = Mock(get=Mock(return_value="9223"))

        status = {
            "chrome": {"connected": True, "count": "not-a-number"},
            "edge": {"connected": False, "count": None},
        }
        with patch("settings_ui.browser_runtime.get_capture_status", return_value=status), \
             patch("settings_ui.messagebox.showinfo") as mock_info:
            win._test_browser_capture()

        mock_info.assert_called_once()
        title, msg = mock_info.call_args.args[:2]
        assert title == "Browser capture status"
        assert "Chrome: Connected, URLs=0" in msg
        assert "Edge: Not connected, URLs=0" in msg

    def test_test_browser_capture_handles_non_dict_browser_entries(self):
        import settings_ui

        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._chrome_port_var = Mock(get=Mock(return_value="9222"))
        win._edge_port_var = Mock(get=Mock(return_value="9223"))

        status = {
            "chrome": None,
            "edge": "bad-shape",
        }
        with patch("settings_ui.browser_runtime.get_capture_status", return_value=status), \
             patch("settings_ui.messagebox.showinfo") as mock_info:
            win._test_browser_capture()

        mock_info.assert_called_once()
        title, msg = mock_info.call_args.args[:2]
        assert title == "Browser capture status"
        assert "Chrome: Not connected, URLs=0" in msg
        assert "Edge: Not connected, URLs=0" in msg
