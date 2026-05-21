"""Global hotkey management using the `keyboard` library."""

from __future__ import annotations

import logging
from typing import Callable

import keyboard

log = logging.getLogger(__name__)

# Internal registry: combo string → hotkey_id returned by keyboard.add_hotkey
_registered: dict[str, int] = {}


def register(combo: str, callback: Callable[[], None]) -> None:
    """Register a global hotkey. If combo is already registered, replaces it."""
    _unregister(combo)
    try:
        hk_id = keyboard.add_hotkey(combo, callback, suppress=False)
        _registered[combo] = hk_id
        log.info("Registered hotkey: %s", combo)
    except Exception as exc:
        log.error("Failed to register hotkey %r: %s", combo, exc)


def _unregister(combo: str) -> None:
    """Remove a hotkey if it is currently registered."""
    if combo in _registered:
        try:
            keyboard.remove_hotkey(_registered[combo])
        except Exception:
            pass
        del _registered[combo]
        log.debug("Unregistered hotkey: %s", combo)


def unregister_all() -> None:
    """Remove all registered hotkeys (call on app shutdown or settings change)."""
    for combo in list(_registered.keys()):
        _unregister(combo)
    log.info("All hotkeys unregistered")


def update(save_combo: str, restore_combo: str,
           on_save: Callable[[], None], on_restore: Callable[[], None]) -> None:
    """Re-register save/restore hotkeys (clears all existing first)."""
    unregister_all()
    register(save_combo, on_save)
    register(restore_combo, on_restore)
