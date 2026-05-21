"""Tests for profiles.py — profile and config persistence."""

import json
import pytest
from pathlib import Path


@pytest.fixture()
def profile_dirs(tmp_path, monkeypatch):
    """Redirect APP_DIR to a temp directory for isolation."""
    import profiles
    monkeypatch.setattr(profiles, "APP_DIR", tmp_path / "ScreenSetupSaver")
    monkeypatch.setattr(profiles, "PROFILES_DIR", tmp_path / "ScreenSetupSaver" / "profiles")
    monkeypatch.setattr(profiles, "CONFIG_FILE", tmp_path / "ScreenSetupSaver" / "config.json")
    return tmp_path / "ScreenSetupSaver"


class TestListProfiles:
    def test_empty_returns_empty_list(self, profile_dirs):
        import profiles
        assert profiles.list_profiles() == []

    def test_returns_sorted_names(self, profile_dirs):
        import profiles
        profiles.save_profile("work", {"windows": []})
        profiles.save_profile("gaming", {"windows": []})
        assert profiles.list_profiles() == ["gaming", "work"]


class TestSaveLoadProfile:
    def test_roundtrip(self, profile_dirs):
        import profiles
        data = {"windows": [{"title": "Notepad", "rect": [0, 0, 800, 600], "state": "normal"}]}
        profiles.save_profile("test", data)
        loaded = profiles.load_profile("test")
        assert loaded == data

    def test_load_missing_raises(self, profile_dirs):
        import profiles
        with pytest.raises(FileNotFoundError):
            profiles.load_profile("nonexistent")

    def test_save_overwrites(self, profile_dirs):
        import profiles
        profiles.save_profile("p", {"v": 1})
        profiles.save_profile("p", {"v": 2})
        assert profiles.load_profile("p")["v"] == 2


class TestDeleteProfile:
    def test_delete_removes_file(self, profile_dirs):
        import profiles
        profiles.save_profile("to_delete", {})
        profiles.delete_profile("to_delete")
        assert profiles.list_profiles() == []

    def test_delete_missing_raises(self, profile_dirs):
        import profiles
        with pytest.raises(FileNotFoundError):
            profiles.delete_profile("nope")


class TestRenameProfile:
    def test_rename_success(self, profile_dirs):
        import profiles
        profiles.save_profile("old", {"x": 1})
        profiles.rename_profile("old", "new")
        assert profiles.list_profiles() == ["new"]
        assert profiles.load_profile("new")["x"] == 1

    def test_rename_missing_raises(self, profile_dirs):
        import profiles
        with pytest.raises(FileNotFoundError):
            profiles.rename_profile("ghost", "new")

    def test_rename_conflict_raises(self, profile_dirs):
        import profiles
        profiles.save_profile("a", {})
        profiles.save_profile("b", {})
        with pytest.raises(ValueError):
            profiles.rename_profile("a", "b")


class TestConfig:
    def test_defaults_created_when_missing(self, profile_dirs):
        import profiles
        cfg = profiles.load_config()
        assert cfg["hotkey_save"] == "ctrl+alt+s"
        assert cfg["hotkey_restore"] == "ctrl+alt+r"
        assert cfg["last_profile"] is None
        assert cfg["chrome_debug_port"] == 9222
        assert cfg["edge_debug_port"] == 9223

    def test_backfill_missing_keys(self, profile_dirs):
        import profiles
        # Write a config with only one key
        profiles._ensure_dirs()
        profiles.CONFIG_FILE.write_text('{"hotkey_save": "ctrl+s"}', encoding="utf-8")
        cfg = profiles.load_config()
        assert cfg["hotkey_save"] == "ctrl+s"  # preserved
        assert "hotkey_restore" in cfg           # back-filled

    def test_save_config_roundtrip(self, profile_dirs):
        import profiles
        cfg = profiles.load_config()
        cfg["last_profile"] = "work"
        profiles.save_config(cfg)
        reloaded = profiles.load_config()
        assert reloaded["last_profile"] == "work"


class TestPathSafety:
    def test_traversal_in_load_raises(self, profile_dirs):
        import profiles
        with pytest.raises(ValueError, match="Invalid profile name"):
            profiles.load_profile("../escape")

    def test_traversal_in_save_raises(self, profile_dirs):
        import profiles
        with pytest.raises(ValueError, match="Invalid profile name"):
            profiles.save_profile("../escape", {})

    def test_traversal_in_delete_raises(self, profile_dirs):
        import profiles
        with pytest.raises(ValueError, match="Invalid profile name"):
            profiles.delete_profile("../escape")

    def test_traversal_in_rename_raises(self, profile_dirs):
        import profiles
        profiles.save_profile("legit", {})
        with pytest.raises(ValueError):
            profiles.rename_profile("legit", "../escape")


class TestCorruptFiles:
    def test_load_corrupt_profile_raises_valueerror(self, profile_dirs):
        import profiles
        profiles._ensure_dirs()
        (profiles.PROFILES_DIR / "bad.json").write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            profiles.load_profile("bad")

    def test_load_corrupt_config_returns_defaults(self, profile_dirs):
        import profiles
        profiles._ensure_dirs()
        profiles.CONFIG_FILE.write_text("not json", encoding="utf-8")
        cfg = profiles.load_config()
        assert cfg["hotkey_save"] == "ctrl+alt+s"
