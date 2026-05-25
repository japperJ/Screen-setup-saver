"""Settings window — Profiles, Hotkeys, and Browser Setup tabs."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable

import profiles as prof
import startup

log = logging.getLogger(__name__)


class SettingsWindow:
    """Manages the settings Toplevel window.

    The window is created once and shown/hidden. Never destroyed.

    Args:
        root:             Hidden tk.Tk() root (keeps event loop alive).
        on_save:          Called when user clicks Save in Profiles tab.
        on_restore:       Called with profile name when user clicks Restore.
        on_hotkeys_change: Called with (save_combo, restore_combo) when hotkeys saved.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_save: Callable[[], None],
        on_restore: Callable[[str], None],
        on_hotkeys_change: Callable[[str, str], None],
    ) -> None:
        self._root = root
        self._on_save = on_save
        self._on_restore = on_restore
        self._on_hotkeys_change = on_hotkeys_change

        self._win: tk.Toplevel | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self) -> None:
        """Show (or bring to front) the settings window."""
        if self._win is None or not self._win.winfo_exists():
            self._build()
        else:
            self._win.deiconify()
            self._win.lift()
            self._win.focus_force()
            self._refresh_profiles()

    def hide(self) -> None:
        """Hide the settings window without destroying it."""
        if self._win and self._win.winfo_exists():
            self._win.withdraw()

    # ── Window construction ───────────────────────────────────────────────────

    def _build(self) -> None:
        win = tk.Toplevel(self._root)
        win.title("Screen Setup Saver — Settings")
        win.geometry("620x500")
        win.minsize(620, 500)
        win.protocol("WM_DELETE_WINDOW", self.hide)
        self._win = win

        self._apply_theme(win)

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_general_tab(nb)
        self._build_profiles_tab(nb)
        self._build_hotkeys_tab(nb)
        self._build_browser_tab(nb)

    def _apply_theme(self, win: tk.Toplevel) -> None:
        style = ttk.Style(win)
        themes = style.theme_names()
        if "vista" in themes:
            style.theme_use("vista")
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.configure("TButton", padding=(10, 5))
        style.configure("Treeview", rowheight=26)

    # ── General tab ───────────────────────────────────────────────────────────

    def _build_general_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, padding=12)
        nb.add(frame, text="General")

        ttk.Label(
            frame,
            text="Startup",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text="Launch Screen Setup Saver automatically when you sign in.",
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        cfg = prof.load_config()
        initial_startup = bool(cfg.get("start_with_windows", False))
        try:
            initial_startup = startup.startup_enabled()
        except Exception as exc:
            log.warning("Could not query startup task state: %s", exc)

        self._start_with_windows_var = tk.BooleanVar(value=initial_startup)
        ttk.Checkbutton(
            frame,
            text="Start with Windows (current user)",
            variable=self._start_with_windows_var,
        ).pack(anchor="w")

        ttk.Button(
            frame,
            text="Save startup setting",
            command=self._save_startup_settings,
        ).pack(anchor="w", pady=(12, 0))

    # ── Profiles tab ──────────────────────────────────────────────────────────

    def _build_profiles_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Profiles")

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._profile_list = ttk.Treeview(
            list_frame,
            columns=("name",),
            show="headings",
            selectmode="browse",
            height=12,
        )
        self._profile_list.heading("name", text="Saved profiles")
        self._profile_list.column("name", anchor="w", stretch=True)
        self._profile_list.configure(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._profile_list.yview)
        self._profile_list.pack(side="left", fill="both", expand=True, padx=(0, 8))
        scrollbar.pack(side="right", fill="y")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 2))
        for col in range(4):
            btn_frame.columnconfigure(col, weight=1)

        ttk.Button(btn_frame, text="Save current layout", command=self._save_layout).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Restore", command=self._restore_selected).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Rename", command=self._rename_selected).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).grid(
            row=0, column=3, padx=4, sticky="ew"
        )

        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        if self._win is None or not self._win.winfo_exists():
            return
        self._profile_list.delete(*self._profile_list.get_children())
        for name in prof.list_profiles():
            self._profile_list.insert("", "end", values=(name,))

    def _selected_profile(self) -> str | None:
        sel = self._profile_list.selection()
        if not sel:
            return None
        values = self._profile_list.item(sel[0], "values")
        return values[0] if values else None

    def _save_layout(self) -> None:
        name = simpledialog.askstring(
            "Save layout", "Profile name:", parent=self._win
        )
        if not name or not name.strip():
            return
        name = name.strip()
        # The actual save with the chosen name is handled by on_save via main.py
        # which calls capture + save_profile; we pass name via a different path.
        # Simpler: call save directly here.
        try:
            import capture
            import browser
            cfg = prof.load_config()
            data = {
                "windows": capture.capture_windows(),
                "browser_tabs": browser.capture_browser_tabs(
                    chrome_port=cfg.get("chrome_debug_port", 9222),
                    edge_port=cfg.get("edge_debug_port", 9223),
                ),
            }
            prof.save_profile(name, data)
            self._refresh_profiles()
            messagebox.showinfo("Saved", f"Profile '{name}' saved.", parent=self._win)
        except Exception as exc:
            log.error("Save failed: %s", exc)
            messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)

    def _set_startup_preference(self, enabled: bool) -> None:
        if enabled:
            startup.enable_startup()
        else:
            startup.disable_startup()
        cfg = prof.load_config()
        cfg["start_with_windows"] = bool(enabled)
        prof.save_config(cfg)

    def _save_startup_settings(self) -> None:
        enabled = bool(self._start_with_windows_var.get())
        try:
            self._set_startup_preference(enabled)
            messagebox.showinfo(
                "Saved",
                "Startup setting updated.",
                parent=self._win,
            )
        except Exception as exc:
            log.error("Failed to update startup setting: %s", exc)
            messagebox.showerror(
                "Error",
                f"Failed to update startup setting: {exc}",
                parent=self._win,
            )

    def _restore_selected(self) -> None:
        name = self._selected_profile()
        if not name:
            messagebox.showwarning("No selection", "Select a profile to restore.", parent=self._win)
            return
        self._on_restore(name)

    def _rename_selected(self) -> None:
        old = self._selected_profile()
        if not old:
            messagebox.showwarning("No selection", "Select a profile to rename.", parent=self._win)
            return
        new = simpledialog.askstring("Rename", f"New name for '{old}':", parent=self._win)
        if not new or not new.strip():
            return
        new = new.strip()
        try:
            prof.rename_profile(old, new)
            self._refresh_profiles()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self._win)

    def _delete_selected(self) -> None:
        name = self._selected_profile()
        if not name:
            messagebox.showwarning("No selection", "Select a profile to delete.", parent=self._win)
            return
        if not messagebox.askyesno("Confirm", f"Delete profile '{name}'?", parent=self._win):
            return
        try:
            prof.delete_profile(name)
            self._refresh_profiles()
        except FileNotFoundError:
            messagebox.showerror("Error", "Profile not found.", parent=self._win)

    # ── Hotkeys tab ───────────────────────────────────────────────────────────

    def _build_hotkeys_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Hotkeys")

        cfg = prof.load_config()

        ttk.Label(frame, text="Save hotkey:").grid(row=0, column=0, padx=8, pady=12, sticky="w")
        self._save_hotkey_var = tk.StringVar(value=cfg.get("hotkey_save", "ctrl+alt+s"))
        ttk.Entry(frame, textvariable=self._save_hotkey_var, width=20).grid(
            row=0, column=1, padx=8, pady=12, sticky="w"
        )

        ttk.Label(frame, text="Restore hotkey:").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        self._restore_hotkey_var = tk.StringVar(value=cfg.get("hotkey_restore", "ctrl+alt+r"))
        ttk.Entry(frame, textvariable=self._restore_hotkey_var, width=20).grid(
            row=1, column=1, padx=8, pady=4, sticky="w"
        )

        ttk.Button(frame, text="Save hotkeys", command=self._save_hotkeys).grid(
            row=2, column=0, columnspan=2, pady=16
        )

        ttk.Label(
            frame,
            text="Changes take effect immediately after saving.",
            foreground="gray",
        ).grid(row=3, column=0, columnspan=2, padx=8)

    def _save_hotkeys(self) -> None:
        save_combo    = self._save_hotkey_var.get().strip()
        restore_combo = self._restore_hotkey_var.get().strip()
        if not save_combo or not restore_combo:
            messagebox.showwarning("Invalid", "Both hotkeys must be non-empty.", parent=self._win)
            return
        try:
            cfg = prof.load_config()
            cfg["hotkey_save"]    = save_combo
            cfg["hotkey_restore"] = restore_combo
            prof.save_config(cfg)
            self._on_hotkeys_change(save_combo, restore_combo)
            messagebox.showinfo("Saved", "Hotkeys updated.", parent=self._win)
        except Exception as exc:
            log.error("Failed to save hotkeys: %s", exc)
            messagebox.showerror("Error", f"Failed to save hotkeys: {exc}", parent=self._win)

    # ── Browser Setup tab ─────────────────────────────────────────────────────

    def _build_browser_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Browser Setup")

        instructions = (
            "To capture browser tabs, launch your browser with remote debugging enabled.\n\n"
            "Chrome shortcut target:\n"
            '  chrome.exe --remote-debugging-port=9222\n\n'
            "Edge shortcut target:\n"
            '  msedge.exe --remote-debugging-port=9223\n\n'
            "Tip: Create a desktop shortcut and add the flag to the Target field."
        )
        ttk.Label(frame, text=instructions, justify="left", wraplength=430).pack(
            padx=12, pady=12, anchor="w"
        )

        cfg = prof.load_config()

        port_frame = ttk.Frame(frame)
        port_frame.pack(fill="x", padx=12, pady=4)

        ttk.Label(port_frame, text="Chrome debug port:").grid(row=0, column=0, sticky="w", pady=4)
        self._chrome_port_var = tk.StringVar(value=str(cfg.get("chrome_debug_port", 9222)))
        ttk.Entry(port_frame, textvariable=self._chrome_port_var, width=8).grid(
            row=0, column=1, padx=8, sticky="w"
        )

        ttk.Label(port_frame, text="Edge debug port:").grid(row=1, column=0, sticky="w", pady=4)
        self._edge_port_var = tk.StringVar(value=str(cfg.get("edge_debug_port", 9223)))
        ttk.Entry(port_frame, textvariable=self._edge_port_var, width=8).grid(
            row=1, column=1, padx=8, sticky="w"
        )

        ttk.Button(frame, text="Save ports", command=self._save_ports).pack(pady=8)

    def _save_ports(self) -> None:
        try:
            chrome_port = int(self._chrome_port_var.get())
            edge_port   = int(self._edge_port_var.get())
        except ValueError:
            messagebox.showwarning("Invalid", "Ports must be integers.", parent=self._win)
            return
        cfg = prof.load_config()
        cfg["chrome_debug_port"] = chrome_port
        cfg["edge_debug_port"]   = edge_port
        prof.save_config(cfg)
        messagebox.showinfo("Saved", "Debug ports saved.", parent=self._win)
