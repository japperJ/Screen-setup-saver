# Screen Setup Saver — Design Spec

**Date:** 2026-05-21  
**Status:** Approved

---

## Overview

A Windows 11 system tray utility that saves and restores your full screen layout: window positions, running applications, and browser tabs (Chrome + Edge). Supports multiple named profiles, configurable global hotkeys, and a settings/management window.

---

## Goals

- Save a named snapshot of all open windows (position, size, state, executable path)
- Capture all open browser tabs in Chrome and Edge via the Chrome DevTools Protocol (CDP)
- Restore a profile: reopen apps, reposition windows, reopen browser tabs
- Manage multiple named profiles (create, rename, delete)
- Configurable global hotkeys for save, restore, and open-settings actions
- Runs silently as a system tray app; settings window opened on demand

---

## Non-Goals

- Cross-platform support (Windows 11 only)
- Virtual desktop / workspace awareness
- Browser extensions
- Cloud sync of profiles

---

## Architecture

### Stack

- **Language:** Python 3.11+
- **Tray icon:** `pystray`
- **Windows API:** `pywin32` (win32gui, win32process, win32con)
- **Global hotkeys:** `keyboard`
- **Browser CDP:** `websocket-client`
- **Settings UI:** `tkinter` (built-in)
- **Tray icon image:** `Pillow`

### Module Structure

```
screen_setup_saver/
├── main.py            # Entry point — wires tray, hotkeys, settings
├── tray.py            # pystray icon + right-click menu
├── capture.py         # Enumerate windows, record exe/title/rect/state
├── browser.py         # CDP connection to Chrome/Edge, fetch all tabs
├── restore.py         # Reopen apps via subprocess, reposition windows, open tabs
├── profiles.py        # Load/save JSON profiles to %APPDATA%
├── hotkeys.py         # Register/unregister global hotkeys (keyboard lib)
└── settings_ui.py     # tkinter settings window (Profiles, Hotkeys, Browser Setup tabs)
```

### Data Storage

Profiles are stored as individual JSON files in:
```
%APPDATA%\ScreenSetupSaver\profiles\<profile-name>.json
```

App config (hotkeys, last-used profile) stored in:
```
%APPDATA%\ScreenSetupSaver\config.json
```

---

## Profile Format

```json
{
  "name": "Work Setup",
  "saved_at": "2026-05-21T10:00:00",
  "windows": [
    {
      "title": "Visual Studio Code",
      "exe": "C:\\Users\\...\\Code.exe",
      "rect": [0, 0, 1920, 1080],
      "state": "maximized"
    }
  ],
  "browsers": [
    {
      "app": "chrome",
      "exe": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "rect": [1920, 0, 1920, 1080],
      "state": "normal",
      "tabs": [
        "https://github.com",
        "https://docs.python.org"
      ]
    }
  ]
}
```

`state` is one of: `"normal"`, `"maximized"`, `"minimized"`.

---

## Modules

### `capture.py`

- Uses `win32gui.EnumWindows` to iterate all top-level visible windows
- For each window: get title, rect (`GetWindowRect`), state (`IsZoomed`/`IsIconic`), and owning process exe path (`win32process.GetModuleFileNameEx`)
- Skips system/shell windows (no title, UWP shell, etc.) using a filter list
- Detects Chrome/Edge windows by exe name and marks them for CDP capture
- Returns a structured dict ready for `profiles.py`

### `browser.py`

- Connects to `http://localhost:9222/json` (Chrome) and `http://localhost:9223/json` (Edge)
- Parses the JSON list of open tabs — each has `url`, `title`, `windowId`
- Groups tabs by `windowId` to match them with the corresponding window rect from `capture.py`
- If a browser is not running with the debug port, returns an empty list with a warning (does not block capture of other windows)

**CDP one-time setup:**  
The **Browser Setup tab** in settings creates desktop shortcuts for Chrome and Edge with the following flags:
- Chrome: `--remote-debugging-port=9222`
- Edge: `--remote-debugging-port=9223`

A first-run wizard prompts the user to replace their usual browser shortcuts. Existing shortcuts are backed up.

### `restore.py`

Restore sequence for a profile:

1. For each **non-browser window**: check if the process is already running (match by exe path). If not, launch via `subprocess.Popen(exe)`. Wait up to 5 seconds for the window to appear.
2. For each **browser window**: launch browser with debug port flag and the saved tab URLs as arguments (`chrome.exe --remote-debugging-port=9222 url1 url2 ...`). This opens all tabs in one window.
3. After all windows are open, reposition each using `win32gui.SetWindowPos` and apply saved state (`ShowWindow` for maximize/minimize).
4. Repositioning retries up to 3 times with a short delay if the window handle isn't found yet.

**Known limitation:** Apps that don't restore to the same state from a cold launch (e.g., a specific document open in Notepad) will reopen but may not be in the exact prior state. The spec does not attempt to solve deep app state — only window geometry.

### `hotkeys.py`

- Uses the `keyboard` library to register system-wide hotkeys
- Hotkeys are loaded from `config.json` at startup and re-registered when changed in settings
- Three built-in actions:
  - **Save** (`Ctrl+Alt+S` default): if `last_profile` is set in config, silently overwrites it; otherwise shows a small name-prompt dialog. Tray menu "Save Current Layout" always shows the name-prompt.
  - **Restore Last** (`Ctrl+Alt+R` default): restores the most recently saved/restored profile
  - **Open Settings** (`Ctrl+Alt+W` default): shows the settings window
- Optional **Quick-Restore slots** `Ctrl+Alt+1` through `Ctrl+Alt+9`: each slot can be bound to a named profile in settings
- Conflict detection: warns if the chosen combo is already registered

### `tray.py`

Right-click menu structure:
```
💾 Save Current Layout      → prompts for name → saves profile
🔁 Restore →                → submenu: [Work Setup, Gaming, Home Office, ...]
⚙ Open Settings
─────────────────
Exit
```

### `settings_ui.py`

Three tabs:

**Profiles tab:**
- List of profiles (name, saved date, window count, tab count)
- Buttons: Save Current, Restore Selected, Rename, Delete
- Preview panel: shows window titles and browser tabs for the selected profile

**Hotkeys tab:**
- Click-to-record fields for each action
- Conflict detection highlighted inline
- Save button applies and re-registers hotkeys

**Browser Setup tab:**
- Status indicators: Chrome debug port connected / not connected, Edge debug port connected / not connected
- "Create Debug Shortcuts" button: creates Start Menu + Desktop shortcuts with the debug port flags
- Instructions for users who prefer to modify their existing shortcuts manually

---

## Config Format

```json
{
  "last_profile": "Work Setup",
  "hotkeys": {
    "save": "ctrl+alt+s",
    "restore_last": "ctrl+alt+r",
    "open_settings": "ctrl+alt+w",
    "quick_restore": {
      "1": "Work Setup",
      "2": "Gaming"
    }
  }
}
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Browser not running with debug port | Skip tab capture; show warning icon in tray tooltip |
| App exe path no longer exists on restore | Skip that window; show summary after restore |
| Window doesn't appear within 5s | Skip repositioning; log to `%APPDATA%\ScreenSetupSaver\app.log` |
| Hotkey conflict | Show inline error in settings; do not apply |
| Profile file corrupted | Skip on load; show error in settings list |

---

## Startup & Distribution

- `main.py` is the entry point; can be run with `python main.py`
- A `run.bat` script is included for easy double-click launch
- Optional: build to a single `.exe` with PyInstaller (`pyinstaller --onefile --windowed main.py`)
- Add to Windows startup via a shortcut in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`
- A `requirements.txt` lists all dependencies

---

## File Layout

```
Screen-setup-saver/
├── main.py
├── tray.py
├── capture.py
├── browser.py
├── restore.py
├── profiles.py
├── hotkeys.py
├── settings_ui.py
├── assets/
│   └── icon.png          # Tray icon (16×16 and 32×32); auto-generated with Pillow if missing
├── requirements.txt
├── run.bat
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-21-screen-setup-saver-design.md
```
