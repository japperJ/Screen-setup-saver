"""Settings window — Profiles, Hotkeys, and Browser Setup tabs."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

import browser_runtime
import capture
import profiles as prof
import profile_builder
import startup

log = logging.getLogger(__name__)


def _format_profile_details(profile: dict) -> str:
    """Build a human-readable summary for a saved profile."""
    windows = profile.get("windows", []) if isinstance(profile, dict) else []
    browser_tabs = profile.get("browser_tabs", {}) if isinstance(profile, dict) else {}
    if not isinstance(windows, list):
        windows = []
    if not isinstance(browser_tabs, dict):
        browser_tabs = {}

    app_names: set[str] = set()
    for win in windows:
        if not isinstance(win, dict):
            continue
        exe = str(win.get("exe", "")).strip()
        if exe:
            app_names.add(os.path.basename(exe))

    ordered_browsers = ["chrome", "edge"]
    browser_keys = ordered_browsers + sorted(k for k in browser_tabs.keys() if k not in ordered_browsers)
    url_total = 0
    urls_by_browser: dict[str, list[str]] = {}
    for key in browser_keys:
        urls = browser_tabs.get(key, [])
        if not isinstance(urls, list):
            continue
        clean_urls = [str(url).strip() for url in urls if str(url).strip()]
        urls_by_browser[key] = clean_urls
        url_total += len(clean_urls)

    lines = [
        f"Windows captured: {len(windows)}",
        f"Browser tabs captured: {url_total}",
        "",
    ]

    if app_names:
        lines.append("Apps:")
        for name in sorted(app_names, key=str.lower):
            lines.append(f"- {name}")
    else:
        lines.append("Apps: none")

    lines.append("")
    if url_total == 0:
        lines.append("No browser URLs saved in this profile.")
        lines.append("Launch browsers in Capture Mode before saving.")
    else:
        lines.append("Browser URLs:")
        for browser in browser_keys:
            urls = urls_by_browser.get(browser, [])
            if not urls:
                continue
            lines.append(f"{browser.title()} ({len(urls)}):")
            for url in urls:
                lines.append(f"- {url}")

    return "\n".join(lines)


class WindowPickerDialog:
    """Modal dialog for selecting which windows to include in a saved profile.

    Usage::

        picker = WindowPickerDialog(parent, windows)
        selected_hwnds = picker.result  # set[int] or None if cancelled
    """

    def __init__(self, parent: tk.Misc, windows: list[dict]) -> None:
        self._result: set[int] | None = None
        self._vars: dict[int, tk.BooleanVar] = {}

        self._dlg = tk.Toplevel(parent)
        self._dlg.title("Select windows to save")
        self._dlg.resizable(False, False)
        self._dlg.grab_set()

        self._build(windows)
        parent.wait_window(self._dlg)

    def _build(self, windows: list[dict]) -> None:
        # Group windows by exe basename
        groups: dict[str, list[dict]] = {}
        for w in windows:
            exe = os.path.basename(w.get("exe", "")).lower() or "unknown"
            groups.setdefault(exe, []).append(w)

        container = ttk.Frame(self._dlg, padding=8)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, width=460, height=400)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Global select / deselect
        top_bar = ttk.Frame(scroll_frame)
        top_bar.pack(fill="x", padx=4, pady=(4, 8))
        ttk.Button(top_bar, text="Select all", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(top_bar, text="Deselect all", command=lambda: self._set_all(False)).pack(
            side="left", padx=(4, 0)
        )

        # Per-group sections
        for exe_name, wins in sorted(groups.items()):
            grp = ttk.LabelFrame(scroll_frame, text=exe_name, padding=4)
            grp.pack(fill="x", padx=4, pady=4)

            hdr = ttk.Frame(grp)
            hdr.pack(fill="x")
            ttk.Button(
                hdr, text="Deselect all", command=lambda ws=wins: self._set_group(ws, False)
            ).pack(side="right")
            ttk.Button(
                hdr, text="Select all", command=lambda ws=wins: self._set_group(ws, True)
            ).pack(side="right", padx=(0, 4))

            for w in wins:
                hwnd = w.get("hwnd", 0)
                var = tk.BooleanVar(value=True)
                self._vars[hwnd] = var
                title = w.get("title", "") or f"(hwnd={hwnd})"
                ttk.Checkbutton(grp, text=title, variable=var).pack(anchor="w", padx=8)

        # Save / Cancel buttons
        btn_frame = ttk.Frame(self._dlg, padding=8)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="right", padx=(0, 4))

    def _set_all(self, value: bool) -> None:
        for var in self._vars.values():
            var.set(value)

    def _set_group(self, wins: list[dict], value: bool) -> None:
        for w in wins:
            hwnd = w.get("hwnd", 0)
            if hwnd in self._vars:
                self._vars[hwnd].set(value)

    def _save(self) -> None:
        self._result = {hwnd for hwnd, var in self._vars.items() if var.get()}
        self._dlg.destroy()

    def _cancel(self) -> None:
        self._result = None
        self._dlg.destroy()

    @property
    def result(self) -> set[int] | None:
        return self._result


class SettingsWindow:
    """Manages the settings Toplevel window.

    The window is created once and shown/hidden. Never destroyed.

    Args:
        root:             Hidden tk.Tk() root (keeps event loop alive).
        on_save:          Called with updated config when save succeeds.
        on_restore:       Called with profile name when user clicks Restore.
        on_hotkeys_change: Called with (save_combo, restore_combo) when hotkeys saved.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_save: Callable[[dict[str, Any]], None],
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

        split = ttk.Panedwindow(frame, orient="horizontal")
        split.pack(fill="both", expand=True)

        left_pane = ttk.Frame(split)
        right_pane = ttk.Frame(split)
        split.add(left_pane, weight=2)
        split.add(right_pane, weight=3)

        list_frame = ttk.Frame(left_pane)
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
        self._profile_list.bind("<<TreeviewSelect>>", self._on_profile_select)

        btn_frame = ttk.Frame(left_pane)
        btn_frame.pack(fill="x", pady=(10, 6))
        for col in range(5):
            btn_frame.columnconfigure(col, weight=1)

        ttk.Button(btn_frame, text="Save all", command=self._save_layout).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Save selected…", command=self._save_selected_layout).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Restore", command=self._restore_selected).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Rename", command=self._rename_selected).grid(
            row=0, column=3, padx=4, sticky="ew"
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).grid(
            row=0, column=4, padx=4, sticky="ew"
        )

        details_frame = ttk.LabelFrame(right_pane, text="Selected profile details", padding=8)
        details_frame.pack(fill="both", expand=True)
        details_scrollbar = ttk.Scrollbar(details_frame, orient="vertical")
        self._profile_details = tk.Text(
            details_frame,
            height=12,
            wrap="word",
            relief="flat",
            borderwidth=0,
            background="#f6f6f6",
            yscrollcommand=details_scrollbar.set,
        )
        details_scrollbar.config(command=self._profile_details.yview)
        self._profile_details.pack(side="left", fill="both", expand=True)
        details_scrollbar.pack(side="right", fill="y")
        self._set_profile_details_text("Select a profile to see saved windows and browser URLs.")

        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        if self._win is None or not self._win.winfo_exists():
            return
        self._profile_list.delete(*self._profile_list.get_children())
        for name in prof.list_profiles():
            self._profile_list.insert("", "end", values=(name,))
        self._set_profile_details_text("Select a profile to see saved windows and browser URLs.")

    def _selected_profile(self) -> str | None:
        sel = self._profile_list.selection()
        if not sel:
            return None
        values = self._profile_list.item(sel[0], "values")
        return values[0] if values else None

    def _set_profile_details_text(self, text: str) -> None:
        self._profile_details.config(state="normal")
        self._profile_details.delete("1.0", "end")
        self._profile_details.insert("1.0", text)
        self._profile_details.config(state="disabled")

    def _on_profile_select(self, _: object | None = None) -> None:
        name = self._selected_profile()
        if not name:
            self._set_profile_details_text("Select a profile to see saved windows and browser URLs.")
            return
        try:
            profile = prof.load_profile(name)
            self._set_profile_details_text(_format_profile_details(profile))
        except Exception as exc:
            log.error("Failed to load profile details for %r: %s", name, exc)
            self._set_profile_details_text(f"Failed to load profile details:\n{exc}")

    def _save_layout(self) -> None:
        name = simpledialog.askstring(
            "Save layout", "Profile name:", parent=self._win
        )
        if not name or not name.strip():
            return
        name = name.strip()

        try:
            cfg = prof.load_config()
            data = profile_builder.build_profile_payload(cfg)
        except Exception as exc:
            log.error("Save failed before profile write: %s", exc)
            messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
            return

        try:
            prof.save_profile(name, data)
        except Exception as exc:
            log.error("Save failed while writing profile '%s': %s", name, exc)
            messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
            return

        tab_total = 0
        browser_tabs = data.get("browser_tabs", {}) if isinstance(data, dict) else {}
        if isinstance(browser_tabs, dict):
            for browser_name in ("chrome", "edge"):
                tabs = browser_tabs.get(browser_name, [])
                if isinstance(tabs, list):
                    tab_total += len(tabs)

        cfg["last_profile"] = name
        config_error: Exception | None = None
        try:
            prof.save_config(cfg)
        except Exception as exc:
            config_error = exc
            log.error("Profile '%s' saved, but config update failed: %s", name, exc)

        self._refresh_profiles()

        if config_error is not None:
            messagebox.showwarning(
                "Saved with warning",
                f"Profile '{name}' saved, but updating defaults failed: {config_error}",
                parent=self._win,
            )
            return

        callback_error: Exception | None = None
        try:
            self._on_save(cfg)
        except Exception as exc:
            callback_error = exc
            log.error("Profile saved but on_save callback failed: %s", exc)

        if callback_error is not None:
            messagebox.showwarning(
                "Saved with warning",
                f"Profile '{name}' saved, but refresh callback failed: {callback_error}",
                parent=self._win,
            )
        elif tab_total == 0:
            messagebox.showwarning(
                "Saved without browser URLs",
                "No browser tabs captured. Launch browsers in Capture Mode before saving.",
                parent=self._win,
            )
        else:
            messagebox.showinfo("Saved", f"Profile '{name}' saved.", parent=self._win)

    def _save_selected_layout(self) -> None:
        name = simpledialog.askstring(
            "Save layout", "Profile name:", parent=self._win
        )
        if not name or not name.strip():
            return
        name = name.strip()

        windows = capture.capture_windows()
        if not windows:
            messagebox.showinfo(
                "Nothing to save",
                "No windows are currently open.",
                parent=self._win,
            )
            return

        picker = WindowPickerDialog(self._win, windows)
        selected_hwnds = picker.result
        if selected_hwnds is None:
            return
        if not selected_hwnds:
            messagebox.showerror(
                "Nothing selected",
                "Select at least one window to save.",
                parent=self._win,
            )
            return

        try:
            cfg = prof.load_config()
            data = profile_builder.build_profile_payload(cfg, windows_filter=selected_hwnds)
        except Exception as exc:
            log.error("Save failed before profile write: %s", exc)
            messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
            return

        try:
            prof.save_profile(name, data)
        except Exception as exc:
            log.error("Save failed while writing profile '%s': %s", name, exc)
            messagebox.showerror("Error", f"Failed to save: {exc}", parent=self._win)
            return

        cfg["last_profile"] = name
        config_error: Exception | None = None
        try:
            prof.save_config(cfg)
        except Exception as exc:
            config_error = exc
            log.error("Profile '%s' saved, but config update failed: %s", name, exc)

        self._refresh_profiles()

        if config_error is not None:
            messagebox.showwarning(
                "Saved with warning",
                f"Profile '{name}' saved, but updating defaults failed: {config_error}",
                parent=self._win,
            )
            return

        callback_error: Exception | None = None
        try:
            self._on_save(cfg)
        except Exception as exc:
            callback_error = exc
            log.error("Profile saved but on_save callback failed: %s", exc)

        if callback_error is not None:
            messagebox.showwarning(
                "Saved with warning",
                f"Profile '{name}' saved, but refresh callback failed: {callback_error}",
                parent=self._win,
            )
        else:
            messagebox.showinfo("Saved", f"Profile '{name}' saved.", parent=self._win)

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

        ttk.Button(frame, text="Save ports", command=self._save_ports).pack(pady=(8, 4))

        action_frame = ttk.Frame(frame)
        action_frame.pack(fill="x", padx=12, pady=(4, 12))
        ttk.Button(
            action_frame,
            text="Launch Chrome in Capture Mode",
            command=self._launch_chrome_capture_mode,
        ).pack(anchor="w", pady=2)
        ttk.Button(
            action_frame,
            text="Launch Edge in Capture Mode",
            command=self._launch_edge_capture_mode,
        ).pack(anchor="w", pady=2)
        ttk.Button(
            action_frame,
            text="Test browser capture now",
            command=self._test_browser_capture,
        ).pack(anchor="w", pady=2)

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

    def _launch_chrome_capture_mode(self) -> None:
        try:
            port = int(self._chrome_port_var.get())
        except ValueError:
            messagebox.showwarning("Invalid", "Ports must be integers.", parent=self._win)
            return
        try:
            browser_runtime.launch_browser_capture_mode("chrome", port, "127.0.0.1")
        except Exception as exc:
            log.error("Failed to launch Chrome capture mode: %s", exc)
            messagebox.showerror("Error", f"Failed to launch Chrome: {exc}", parent=self._win)

    def _launch_edge_capture_mode(self) -> None:
        try:
            port = int(self._edge_port_var.get())
        except ValueError:
            messagebox.showwarning("Invalid", "Ports must be integers.", parent=self._win)
            return
        try:
            browser_runtime.launch_browser_capture_mode("edge", port, "127.0.0.1")
        except Exception as exc:
            log.error("Failed to launch Edge capture mode: %s", exc)
            messagebox.showerror("Error", f"Failed to launch Edge: {exc}", parent=self._win)

    def _test_browser_capture(self) -> None:
        try:
            chrome_port = int(self._chrome_port_var.get())
            edge_port = int(self._edge_port_var.get())
        except ValueError:
            messagebox.showwarning("Invalid", "Ports must be integers.", parent=self._win)
            return

        try:
            status = browser_runtime.get_capture_status(chrome_port, edge_port)
        except Exception as exc:
            log.error("Failed to test browser capture: %s", exc)
            messagebox.showerror("Error", f"Failed to test browser capture: {exc}", parent=self._win)
            return

        def _coerce_count(value: Any) -> int:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return 0
            return parsed if parsed >= 0 else 0

        chrome_raw = status.get("chrome", {}) if isinstance(status, dict) else {}
        edge_raw = status.get("edge", {}) if isinstance(status, dict) else {}
        chrome = chrome_raw if isinstance(chrome_raw, dict) else {}
        edge = edge_raw if isinstance(edge_raw, dict) else {}
        chrome_count = _coerce_count(chrome.get("count", 0))
        edge_count = _coerce_count(edge.get("count", 0))
        summary = (
            f"Chrome: {'Connected' if chrome.get('connected') else 'Not connected'}, "
            f"URLs={chrome_count}\n"
            f"Edge: {'Connected' if edge.get('connected') else 'Not connected'}, "
            f"URLs={edge_count}"
        )
        messagebox.showinfo("Browser capture status", summary, parent=self._win)
