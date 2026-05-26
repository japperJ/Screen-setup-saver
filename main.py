"""Screen Setup Saver — entry point."""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

import profiles as prof
import profile_builder
import restore
import hotkeys
import startup
from tray import TrayApp
from settings_ui import SettingsWindow

# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    log_dir = prof.APP_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

log = logging.getLogger(__name__)


# ── App class ──────────────────────────────────────────────────────────────────

class App:
    """Wires all modules together and owns the main tk event loop."""

    def __init__(self) -> None:
        self._cfg = prof.load_config()
        self._sync_startup_registration()

        # Hidden root window — keeps tkinter event loop alive
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.protocol("WM_DELETE_WINDOW", self._quit)

        self._settings = SettingsWindow(
            root=self._root,
            on_save=self._on_settings_save,
            on_restore=self._restore_named,
            on_hotkeys_change=self._update_hotkeys,
        )

        self._tray = TrayApp(
            on_save=self._tray_save,
            on_restore=self._tray_restore,
            on_settings=self._show_settings,
            on_quit=self._quit,
        )

    def _sync_startup_registration(self) -> None:
        """Keep startup registration aligned with saved preference."""
        if not self._cfg.get("start_with_windows", False):
            return
        try:
            startup.enable_startup()
        except Exception as exc:
            log.warning("Could not ensure startup task registration: %s", exc)

    def run(self) -> None:
        """Start tray, register hotkeys, enter tk main loop."""
        self._tray.start()
        self._register_hotkeys()
        log.info("Screen Setup Saver started")
        try:
            self._root.mainloop()
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        hotkeys.unregister_all()
        self._tray.stop()
        log.info("Screen Setup Saver stopped")

    # ── Hotkeys ───────────────────────────────────────────────────────────────

    def _register_hotkeys(self) -> None:
        self._cfg = prof.load_config()
        hotkeys.update(
            save_combo=self._cfg.get("hotkey_save", "ctrl+alt+s"),
            restore_combo=self._cfg.get("hotkey_restore", "ctrl+alt+r"),
            on_save=self._hotkey_save,
            on_restore=self._hotkey_restore,
        )

    def _update_hotkeys(self, save_combo: str, restore_combo: str) -> None:
        """Called by settings UI when hotkeys change."""
        self._cfg["hotkey_save"] = save_combo
        self._cfg["hotkey_restore"] = restore_combo
        hotkeys.update(save_combo, restore_combo, self._hotkey_save, self._hotkey_restore)
        log.info("Hotkeys updated: save=%s restore=%s", save_combo, restore_combo)

    # ── Save paths ────────────────────────────────────────────────────────────

    def _do_save(self, name: str) -> None:
        """Capture current layout and save as profile `name`."""
        try:
            cfg = prof.load_config()
            data = profile_builder.build_profile_payload(cfg)
            prof.save_profile(name, data)
            cfg["last_profile"] = name
            prof.save_config(cfg)
            self._cfg = cfg
            self._tray.notify("Saved", f"Layout saved as '{name}'")
            log.info("Layout saved as %r", name)
        except Exception as exc:
            log.error("Save failed: %s", exc)
            self._tray.notify("Error", f"Save failed: {exc}")

    def _hotkey_save(self) -> None:
        """Save hotkey handler: overwrite last_profile or prompt via root.after."""
        last = self._cfg.get("last_profile")
        if last:
            self._do_save(last)
        else:
            # Must interact with tkinter from main thread
            self._root.after(0, self._prompt_save)

    def _prompt_save(self) -> None:
        name = simpledialog.askstring("Save layout", "Profile name:", parent=self._root)
        if name and name.strip():
            self._do_save(name.strip())

    def _tray_save(self) -> None:
        """Tray 'Save layout' handler: always prompts for name."""
        self._root.after(0, self._prompt_save)

    def _on_settings_save(self, cfg: dict[str, object]) -> None:
        """Sync in-memory config after settings window saves a profile."""
        self._cfg = cfg

    # ── Restore paths ──────────────────────────────────────────────────────────

    def _do_restore(self, name: str) -> None:
        try:
            profile = prof.load_profile(name)
            if messagebox.askyesno("Restore Profile", "Minimize all other windows before restoring?"):
                restore.minimize_other_windows(profile)
            restore.restore_profile(profile)
            self._tray.notify("Restored", f"Layout '{name}' restored")
            log.info("Restored profile %r", name)
        except FileNotFoundError:
            log.warning("Profile not found: %r", name)
            self._tray.notify("Error", f"Profile '{name}' not found")
        except Exception as exc:
            log.error("Restore failed: %s", exc)
            self._tray.notify("Error", f"Restore failed: {exc}")

    def _hotkey_restore(self) -> None:
        last = self._cfg.get("last_profile")
        if last:
            self._do_restore(last)
        else:
            log.info("Restore hotkey pressed but no last_profile set")
            self._tray.notify("Info", "No profile saved yet. Use tray → Save layout first.")

    def _tray_restore(self) -> None:
        last = self._cfg.get("last_profile")
        if last:
            self._root.after(0, lambda: self._do_restore(last))
        else:
            self._root.after(0, self._prompt_restore)

    def _prompt_restore(self) -> None:
        profiles = prof.list_profiles()
        if not profiles:
            self._tray.notify("Info", "No profiles saved yet.")
            return
        # Use simpledialog to pick a profile
        name = simpledialog.askstring(
            "Restore layout",
            "Profile name:\n" + "\n".join(f"  • {p}" for p in profiles),
            parent=self._root,
        )
        if name and name.strip():
            self._do_restore(name.strip())

    def _restore_named(self, name: str) -> None:
        """Called by settings UI Restore button."""
        self._root.after(0, lambda: self._do_restore(name))

    # ── Settings ───────────────────────────────────────────────────────────────

    def _show_settings(self) -> None:
        self._root.after(0, self._settings.show)

    def _quit(self) -> None:
        self._root.after(0, self._root.quit)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logging()
    app = App()
    app.run()


if __name__ == "__main__":
    main()
