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


class TestWindowPickerDialog:
    def _make_dialog(self, windows):
        """Create a WindowPickerDialog instance with mocked tkinter UI."""
        import settings_ui

        dlg = settings_ui.WindowPickerDialog.__new__(settings_ui.WindowPickerDialog)
        dlg._result = None
        dlg._vars = {}
        # Populate _vars as __init__ would, without touching tk
        for w in windows:
            hwnd = w.get("hwnd", 0)
            var = type("FakeVar", (), {"_value": True, "get": lambda self: self._value, "set": lambda self, v: setattr(self, "_value", v)})()
            dlg._vars[hwnd] = var
        return dlg

    def test_set_all_checks_all_vars(self):
        import settings_ui

        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Explorer", "exe": "explorer.exe"},
        ]
        dlg = self._make_dialog(windows)
        dlg._set_all(False)
        assert all(not v.get() for v in dlg._vars.values())
        dlg._set_all(True)
        assert all(v.get() for v in dlg._vars.values())

    def test_set_group_only_affects_group_windows(self):
        import settings_ui

        windows = [
            {"hwnd": 101, "title": "Win1", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Win2", "exe": "notepad.exe"},
            {"hwnd": 103, "title": "Win3", "exe": "explorer.exe"},
        ]
        dlg = self._make_dialog(windows)
        group = [windows[0], windows[1]]
        dlg._set_group(group, False)
        assert not dlg._vars[101].get()
        assert not dlg._vars[102].get()
        assert dlg._vars[103].get()  # unaffected

    def test_save_returns_checked_hwnds(self):
        import settings_ui

        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Explorer", "exe": "explorer.exe"},
        ]
        dlg = self._make_dialog(windows)
        # Uncheck hwnd 102
        dlg._vars[102].set(False)

        # _save needs _dlg.destroy — patch it
        dlg._dlg = type("FakeToplevel", (), {"destroy": lambda self: None})()
        dlg._save()

        assert dlg._result == {101}

    def test_cancel_returns_none(self):
        import settings_ui

        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        dlg = self._make_dialog(windows)
        dlg._dlg = type("FakeToplevel", (), {"destroy": lambda self: None})()
        dlg._cancel()

        assert dlg._result is None

    def test_save_empty_selection_returns_empty_set(self):
        import settings_ui

        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        dlg = self._make_dialog(windows)
        dlg._vars[101].set(False)
        dlg._dlg = type("FakeToplevel", (), {"destroy": lambda self: None})()
        dlg._save()

        assert dlg._result == set()


class TestSaveSelectedLayout:
    def _make_win(self):
        import settings_ui
        win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        win._win = object()
        win._on_save = Mock()
        win._refresh_profiles = Mock()
        return win

    def test_save_all_does_not_pass_windows_filter(self):
        """'Save all' invokes build_profile_payload without a windows_filter."""
        import settings_ui

        win = self._make_win()
        cfg = {}
        payload = {"windows": [], "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        with patch("settings_ui.simpledialog.askstring", return_value="All"), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload) as mock_build, \
             patch("settings_ui.prof.save_profile"), \
             patch("settings_ui.prof.save_config"), \
             patch("settings_ui.messagebox.showwarning"):
            win._save_layout()

        mock_build.assert_called_once_with(cfg)  # no windows_filter kwarg

    def test_save_selected_opens_picker_with_live_windows(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": windows, "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        mock_picker = Mock()
        mock_picker.result = {101}

        with patch("settings_ui.simpledialog.askstring", return_value="MyProfile"), \
             patch("settings_ui.capture.capture_windows", return_value=windows) as mock_capture, \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker) as mock_dlg, \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile"), \
             patch("settings_ui.prof.save_config"), \
             patch("settings_ui.messagebox.showinfo"):
            win._save_selected_layout()

        mock_capture.assert_called_once()
        mock_dlg.assert_called_once_with(win._win, windows)

    def test_save_selected_aborts_on_name_cancel(self):
        import settings_ui

        win = self._make_win()
        with patch("settings_ui.simpledialog.askstring", return_value=None), \
             patch("settings_ui.capture.capture_windows") as mock_capture, \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_capture.assert_not_called()
        mock_save_profile.assert_not_called()

    def test_save_selected_aborts_when_picker_cancelled(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        mock_picker = Mock()
        mock_picker.result = None  # user hit Cancel

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_save_profile.assert_not_called()

    def test_save_selected_passes_hwnd_filter_to_builder(self):
        import settings_ui

        win = self._make_win()
        windows = [
            {"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"},
            {"hwnd": 102, "title": "Edge", "exe": "msedge.exe"},
        ]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": [windows[0]], "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        mock_picker = Mock()
        mock_picker.result = {101}  # only Notepad selected

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload) as mock_build, \
             patch("settings_ui.prof.save_profile"), \
             patch("settings_ui.prof.save_config"), \
             patch("settings_ui.messagebox.showinfo"):
            win._save_selected_layout()

        mock_build.assert_called_once_with(cfg, windows_filter={101})

    def test_save_selected_aborts_when_no_windows_open(self):
        import settings_ui

        win = self._make_win()
        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=[]), \
             patch("settings_ui.messagebox.showinfo") as mock_info, \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_info.assert_called_once()
        mock_save_profile.assert_not_called()

    def test_save_selected_shows_error_when_zero_windows_checked(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        mock_picker = Mock()
        mock_picker.result = set()  # all unchecked

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.messagebox.showerror") as mock_error, \
             patch("settings_ui.prof.save_profile") as mock_save_profile:
            win._save_selected_layout()

        mock_error.assert_called_once()
        mock_save_profile.assert_not_called()

    def test_save_selected_warns_when_browser_selected_but_no_tabs(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Edge", "exe": r"C:\msedge.exe"}]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {
            "windows": [{"hwnd": 101, "title": "Edge", "exe": r"C:\msedge.exe"}],
            "browser_tabs": {"chrome": [], "edge": []},
            "browser_exes": {},
        }
        mock_picker = Mock()
        mock_picker.result = {101}

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile"), \
             patch("settings_ui.prof.save_config"), \
             patch("settings_ui.messagebox.showwarning") as mock_warning, \
             patch("settings_ui.messagebox.showinfo") as mock_info:
            win._save_selected_layout()

        mock_warning.assert_called_once()
        args = mock_warning.call_args.args
        assert args[0] == "Saved without browser URLs"
        mock_info.assert_not_called()

    def test_save_selected_shows_error_on_build_failure(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        mock_picker = Mock()
        mock_picker.result = {101}

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", side_effect=RuntimeError("build error")), \
             patch("settings_ui.prof.save_profile") as mock_save_profile, \
             patch("settings_ui.messagebox.showerror") as mock_error:
            win._save_selected_layout()

        mock_error.assert_called_once()
        call_args = mock_error.call_args
        assert "build error" in str(call_args)
        mock_save_profile.assert_not_called()

    def test_save_selected_shows_error_on_save_failure(self):
        import settings_ui

        win = self._make_win()
        windows = [{"hwnd": 101, "title": "Notepad", "exe": "notepad.exe"}]
        cfg = {"chrome_debug_port": 9222, "edge_debug_port": 9223, "last_profile": None}
        payload = {"windows": windows, "browser_tabs": {"chrome": [], "edge": []}, "browser_exes": {}}
        mock_picker = Mock()
        mock_picker.result = {101}

        with patch("settings_ui.simpledialog.askstring", return_value="Work"), \
             patch("settings_ui.capture.capture_windows", return_value=windows), \
             patch("settings_ui.WindowPickerDialog", return_value=mock_picker), \
             patch("settings_ui.prof.load_config", return_value=cfg), \
             patch("settings_ui.profile_builder.build_profile_payload", return_value=payload), \
             patch("settings_ui.prof.save_profile", side_effect=RuntimeError("save error")), \
             patch("settings_ui.messagebox.showerror") as mock_error:
            win._save_selected_layout()

        mock_error.assert_called_once()


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


class TestEditJsonUI:
    def test_edit_json_selected_calls_show_json_editor(self):
       import settings_ui

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._selected_profile = Mock(return_value="MyProfile")
       win._show_json_editor = Mock()

       win._edit_json_selected()

       win._show_json_editor.assert_called_once_with("MyProfile")

    def test_edit_json_selected_no_op_when_no_selection(self):
       import settings_ui

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._selected_profile = Mock(return_value=None)
       win._show_json_editor = Mock()

       win._edit_json_selected()

       win._show_json_editor.assert_not_called()

    def test_on_profile_right_click_selects_row_and_posts_menu(self):
       import settings_ui
        
       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._win = Mock()
       win._profile_list = Mock()
       win._profile_list.identify_row = Mock(return_value="item1")
       win._profile_list.selection_set = Mock()
       # Mock selection to return a tuple so sel[0] works
       win._profile_list.selection = Mock(return_value=("item1",))
       # Mock item to return values tuple directly
       win._profile_list.item = Mock(return_value=("TestProfile",))
        
       event = Mock()
       event.y = 50
       event.x_root = 100
       event.y_root = 200
        
       with patch("settings_ui.tk.Menu") as mock_menu_class:
           mock_menu = Mock()
           mock_menu_class.return_value = mock_menu
           win._on_profile_right_click(event)
        
       # Verify row was identified and selected
       win._profile_list.identify_row.assert_called_once_with(50)
       win._profile_list.selection_set.assert_called_once_with("item1")
       # Verify menu was posted with correct coordinates
       mock_menu.tk_popup.assert_called_once_with(100, 200)
       # Verify grab_release was called
       mock_menu.grab_release.assert_called_once()

    def test_on_profile_right_click_disables_edit_json_when_no_selection(self):
       import settings_ui
        
       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._win = Mock()
       win._profile_list = Mock()
       # When no selection, return empty tuple
       win._profile_list.selection = Mock(return_value=())
       win._profile_list.item = Mock(return_value=())
       win._profile_list.identify_row = Mock(return_value="item1")
       win._profile_list.selection_set = Mock()
        
       event = Mock()
       event.y = 50
       event.x_root = 100
       event.y_root = 200
        
       with patch("settings_ui.tk.Menu") as mock_menu_class:
           mock_menu = Mock()
           mock_menu_class.return_value = mock_menu
           win._on_profile_right_click(event)
        
       # Verify Edit JSON was added with disabled state
       edit_json_call = None
       for call in mock_menu.add_command.call_args_list:
           if call[1].get("label") == "Edit JSON":
               edit_json_call = call
               break
       assert edit_json_call is not None
       assert edit_json_call[1].get("state") == "disabled"

    def test_show_json_editor_populates_editor_and_swaps_panel(self):
       import settings_ui
       import json

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        
       # Create mock panels
       details_frame = Mock()
       edit_frame = Mock()
       json_editor = Mock()
       error_label = Mock()
       profile_list = Mock()
        
       win._details_frame = details_frame
       win._edit_frame = edit_frame
       win._json_editor = json_editor
       win._json_error_label = error_label
       win._profile_list = profile_list
       win._editing_profile = None
        
       # Mock profile data
       profile_data = {"windows": [{"title": "Test"}], "browser_tabs": {"chrome": []}}
        
       with patch("settings_ui.prof.load_profile", return_value=profile_data) as mock_load:
           win._show_json_editor("TestProfile")
            
           # Verify profile was loaded
           mock_load.assert_called_once_with("TestProfile")
        
       # Verify editing_profile was set
       assert win._editing_profile == "TestProfile"
        
       # Verify editor was populated with JSON
       json_editor.delete.assert_called_once_with("1.0", "end")
       expected_json = json.dumps(profile_data, indent=2, ensure_ascii=False)
       json_editor.insert.assert_called_once_with("1.0", expected_json)
        
       # Verify error label was cleared
       error_label.config.assert_called_with(text="")
        
       # Verify panels were swapped
       details_frame.pack_forget.assert_called_once()
       edit_frame.pack.assert_called_once()
        
       # Verify profile list was disabled
       profile_list.config.assert_called_with(state="disabled")

    def test_cancel_json_edit_restores_details_panel(self):
       import settings_ui

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
        
       # Create mock panels
       details_frame = Mock()
       edit_frame = Mock()
       profile_list = Mock()
        
       win._details_frame = details_frame
       win._edit_frame = edit_frame
       win._profile_list = profile_list
       win._editing_profile = "TestProfile"
       win._on_profile_select = Mock()
        
       win._cancel_json_edit()
        
       # Verify panels were swapped back
       edit_frame.pack_forget.assert_called_once()
       details_frame.pack.assert_called_once()
        
       # Verify editing_profile was cleared
       assert win._editing_profile is None
        
       # Verify profile list was enabled
       profile_list.config.assert_called_with(state="normal")
        
       # Verify details were restored
       win._on_profile_select.assert_called_once()

    def test_show_json_editor_shows_error_on_load_failure(self):
       import settings_ui

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
         
       # Create mock panels
       details_frame = Mock()
       edit_frame = Mock()
       json_editor = Mock()
       error_label = Mock()
       profile_list = Mock()
         
       win._details_frame = details_frame
       win._edit_frame = edit_frame
       win._json_editor = json_editor
       win._json_error_label = error_label
       win._profile_list = profile_list
       win._editing_profile = None
         
       # Mock load_profile to raise an exception
       test_exc = ValueError("Corrupted profile file")
       with patch("settings_ui.prof.load_profile", side_effect=test_exc) as mock_load:
           win._show_json_editor("BadProfile")
             
           # Verify profile was attempted to be loaded
           mock_load.assert_called_once_with("BadProfile")
         
       # Verify error frame was packed (not just error label configured)
       edit_frame.pack.assert_called_once_with(fill="both", expand=True)
       details_frame.pack_forget.assert_called_once()
         
       # Verify error message was set
       error_label.config.assert_called_with(text="Failed to load profile: Corrupted profile file")
         
       # Verify editor was cleared
       json_editor.config.assert_called_with(state="normal")
       json_editor.delete.assert_called_once_with("1.0", "end")
         
       # Verify profile list was disabled
       profile_list.config.assert_called_with(state="disabled")
         
       # Verify editing_profile was NOT set (so Save button is ineffective)
       assert win._editing_profile is None

    def test_show_json_editor_does_not_set_editing_profile_on_error(self):
       import settings_ui

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
         
       # Create mock panels
       details_frame = Mock()
       edit_frame = Mock()
       json_editor = Mock()
       error_label = Mock()
       profile_list = Mock()
         
       win._details_frame = details_frame
       win._edit_frame = edit_frame
       win._json_editor = json_editor
       win._json_error_label = error_label
       win._profile_list = profile_list
       win._editing_profile = "PreviousProfile"
         
       # Mock load_profile to raise an exception
       test_exc = IOError("Cannot read profile")
       with patch("settings_ui.prof.load_profile", side_effect=test_exc):
           win._show_json_editor("FailProfile")
         
       # Verify editing_profile was NOT set or changed
       # (it should remain its previous value, or be set to None)
       # The key is: _editing_profile should NOT be set to "FailProfile"
       assert win._editing_profile != "FailProfile"

    def test_save_json_edit_valid_saves_profile_and_closes_editor(self):
       import settings_ui
       import json
       from unittest.mock import patch

       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._json_editor = Mock()
       win._json_error_label = Mock()
       win._editing_profile = "profile1"
       win._cancel_json_edit = Mock()

       # Valid JSON payload
       valid_data = {"windows": [{"title": "Test", "exe": "test.exe"}], "browser_tabs": {"chrome": []}}
       valid_json_str = json.dumps(valid_data)
       win._json_editor.get.return_value = valid_json_str

       # Mock prof.save_profile
       with patch("settings_ui.prof.save_profile") as mock_save:
           # Action
           win._save_json_edit()

           # Assert
           mock_save.assert_called_once_with("profile1", valid_data)
        
       win._cancel_json_edit.assert_called_once()
       # Error label should not be set on success
       win._json_error_label.config.assert_not_called()

    def test_save_json_edit_invalid_json_shows_error(self):
       import settings_ui

       # Setup
       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._json_editor = Mock()
       win._json_error_label = Mock()
       win._editing_profile = "profile1"
       win._cancel_json_edit = Mock()

       # Invalid JSON
       invalid_json_str = "{invalid}"
       win._json_editor.get.return_value = invalid_json_str

       # Action
       win._save_json_edit()

       # Assert
       win._json_error_label.config.assert_called_once()
       error_call = win._json_error_label.config.call_args
       error_text = error_call[1].get("text", "")
       assert "JSON Parse Error:" in error_text
       win._cancel_json_edit.assert_not_called()
       # editing_profile should still be set so user can retry
       assert win._editing_profile == "profile1"

    def test_save_json_edit_save_error_shows_error(self):
       import settings_ui
       import json
       from unittest.mock import patch

       # Setup
       win = settings_ui.SettingsWindow.__new__(settings_ui.SettingsWindow)
       win._json_editor = Mock()
       win._json_error_label = Mock()
       win._editing_profile = "profile1"
       win._cancel_json_edit = Mock()

       # Valid JSON payload
       valid_data = {"windows": [], "browser_tabs": {"chrome": []}}
       valid_json_str = json.dumps(valid_data)
       win._json_editor.get.return_value = valid_json_str

       # Mock prof.save_profile to raise an exception
       save_error = IOError("Failed to write profile")
       with patch("settings_ui.prof.save_profile", side_effect=save_error):
           # Action
           win._save_json_edit()

       # Assert
       # Error label should be set with save error message
       win._json_error_label.config.assert_called_once()
       error_call = win._json_error_label.config.call_args
       error_text = error_call[1].get("text", "")
       assert "Save Error:" in error_text
       assert "Failed to write profile" in error_text

       # Editor should remain open (cancel should NOT be called)
       win._cancel_json_edit.assert_not_called()

       # editing_profile should still be set so user can retry
       assert win._editing_profile == "profile1"
