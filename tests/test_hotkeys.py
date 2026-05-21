"""Tests for hotkeys.py — global hotkey registration and management."""

import sys
from unittest.mock import MagicMock, patch, call
import pytest


@pytest.fixture(autouse=True)
def clear_registry():
    """Reset the internal hotkey registry before each test."""
    import hotkeys
    hotkeys._registered.clear()
    yield
    hotkeys._registered.clear()


class TestRegister:
    def test_registers_hotkey(self):
        import hotkeys
        cb = MagicMock()
        mock_id = 42

        with patch("hotkeys.keyboard.add_hotkey", return_value=mock_id) as mock_add:
            hotkeys.register("ctrl+alt+s", cb)

        mock_add.assert_called_once_with("ctrl+alt+s", cb, suppress=False)
        assert hotkeys._registered["ctrl+alt+s"] == mock_id

    def test_replaces_existing_hotkey(self):
        import hotkeys
        cb1, cb2 = MagicMock(), MagicMock()

        with patch("hotkeys.keyboard.add_hotkey", return_value=1) as mock_add, \
             patch("hotkeys.keyboard.remove_hotkey") as mock_remove:
            hotkeys.register("ctrl+alt+s", cb1)
            hotkeys.register("ctrl+alt+s", cb2)  # should replace

        assert mock_remove.call_count == 1  # old one removed
        assert mock_add.call_count == 2

    def test_handles_registration_error(self):
        import hotkeys
        with patch("hotkeys.keyboard.add_hotkey", side_effect=Exception("permission denied")):
            # Should not raise
            hotkeys.register("ctrl+alt+s", MagicMock())

        assert "ctrl+alt+s" not in hotkeys._registered

    def test_multiple_different_hotkeys(self):
        import hotkeys
        with patch("hotkeys.keyboard.add_hotkey", side_effect=[1, 2]):
            hotkeys.register("ctrl+alt+s", MagicMock())
            hotkeys.register("ctrl+alt+r", MagicMock())

        assert len(hotkeys._registered) == 2


class TestUnregisterAll:
    def test_removes_all_hotkeys(self):
        import hotkeys
        hotkeys._registered["ctrl+alt+s"] = 1
        hotkeys._registered["ctrl+alt+r"] = 2

        with patch("hotkeys.keyboard.remove_hotkey") as mock_remove:
            hotkeys.unregister_all()

        assert mock_remove.call_count == 2
        assert hotkeys._registered == {}

    def test_empty_registry_no_error(self):
        import hotkeys
        with patch("hotkeys.keyboard.remove_hotkey") as mock_remove:
            hotkeys.unregister_all()
        mock_remove.assert_not_called()

    def test_handles_remove_error_gracefully(self):
        import hotkeys
        hotkeys._registered["ctrl+alt+s"] = 1

        with patch("hotkeys.keyboard.remove_hotkey", side_effect=Exception("error")):
            hotkeys.unregister_all()  # should not raise

        assert hotkeys._registered == {}


class TestUpdate:
    def test_registers_both_hotkeys(self):
        import hotkeys
        on_save, on_restore = MagicMock(), MagicMock()

        with patch("hotkeys.keyboard.add_hotkey", side_effect=[1, 2]) as mock_add:
            hotkeys.update("ctrl+alt+s", "ctrl+alt+r", on_save, on_restore)

        assert mock_add.call_count == 2
        calls = mock_add.call_args_list
        assert calls[0][0] == ("ctrl+alt+s", on_save)
        assert calls[1][0] == ("ctrl+alt+r", on_restore)

    def test_clears_old_hotkeys_before_registering(self):
        import hotkeys
        hotkeys._registered["old+combo"] = 99

        with patch("hotkeys.keyboard.remove_hotkey") as mock_remove, \
             patch("hotkeys.keyboard.add_hotkey", side_effect=[1, 2]):
            hotkeys.update("ctrl+alt+s", "ctrl+alt+r", MagicMock(), MagicMock())

        mock_remove.assert_called_once_with(99)
        assert "old+combo" not in hotkeys._registered
