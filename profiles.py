"""Profile persistence — save/load named window-layout profiles and app config."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

APP_DIR = Path.home() / "AppData" / "Roaming" / "ScreenSetupSaver"
PROFILES_DIR = APP_DIR / "profiles"
CONFIG_FILE = APP_DIR / "config.json"


def _ensure_dirs() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _safe_profile_path(name: str) -> Path:
    """Resolve profile path and guard against directory traversal."""
    path = (PROFILES_DIR / f"{name}.json").resolve()
    try:
        path.relative_to(PROFILES_DIR.resolve())
    except ValueError:
        raise ValueError(f"Invalid profile name: {name!r}")
    return path


# ── Profile I/O ──────────────────────────────────────────────────────────────

def list_profiles() -> list[str]:
    """Return sorted list of profile names (without .json extension)."""
    _ensure_dirs()
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile(name: str) -> dict[str, Any]:
    """Load profile by name. Raises FileNotFoundError if not found, ValueError if corrupt."""
    path = _safe_profile_path(name)
    with path.open("r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Profile {name!r} contains invalid JSON: {exc}") from exc


def save_profile(name: str, data: dict[str, Any]) -> None:
    """Save (overwrite) profile by name."""
    _ensure_dirs()
    path = _safe_profile_path(name)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    log.info("Saved profile %r → %s", name, path)


def delete_profile(name: str) -> None:
    """Delete a profile. Raises FileNotFoundError if not found."""
    path = _safe_profile_path(name)
    path.unlink()
    log.info("Deleted profile %r", name)


def rename_profile(old: str, new: str) -> None:
    """Rename a profile. Raises FileNotFoundError if old not found, ValueError if new exists or invalid."""
    old_path = _safe_profile_path(old)
    new_path = _safe_profile_path(new)
    if new_path.exists():
        raise ValueError(f"Profile {new!r} already exists")
    old_path.rename(new_path)
    log.info("Renamed profile %r → %r", old, new)


# ── Config I/O ────────────────────────────────────────────────────────────────

_DEFAULTS: dict[str, Any] = {
    "hotkey_save": "ctrl+alt+s",
    "hotkey_restore": "ctrl+alt+r",
    "last_profile": None,
    "chrome_debug_port": 9222,
    "edge_debug_port": 9223,
    "start_with_windows": False,
}


def load_config() -> dict[str, Any]:
    """Load config, filling in missing keys with defaults. On corrupt file, reset to defaults."""
    _ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError:
            log.warning("Config file is corrupt; resetting to defaults")
            cfg = dict(_DEFAULTS)
            save_config(cfg)
            return cfg
        # Back-fill any missing keys
        updated = False
        for key, val in _DEFAULTS.items():
            if key not in data:
                data[key] = val
                updated = True
        if updated:
            save_config(data)
        return data
    cfg = dict(_DEFAULTS)
    save_config(cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Persist config to disk."""
    _ensure_dirs()
    with CONFIG_FILE.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    log.debug("Config saved")
