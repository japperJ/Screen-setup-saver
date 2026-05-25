"""Tests for settings_ui startup preference integration."""

from unittest.mock import patch


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
