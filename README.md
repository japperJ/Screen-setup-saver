# Screen Setup Saver

A Windows 11 system tray utility that saves and restores your window layouts — including app positions and browser tabs.

## Features

- **Save layouts** — captures all visible window positions, sizes, and states
- **Restore layouts** — relaunches apps and repositions windows to saved positions
- **Browser tab capture** — saves open Chrome and Edge tabs (requires debug mode, see setup)
- **Multiple named profiles** — save as many layouts as you need
- **Global hotkeys** — configurable keyboard shortcuts (default: `Ctrl+Alt+S` to save, `Ctrl+Alt+R` to restore)
- **System tray** — runs quietly in the background

## Requirements

- Windows 11 (or Windows 10)
- Python 3.11+
- Dependencies: see `requirements.txt`

## Installation

```bat
pip install -r requirements.txt
```

## Running

```bat
run.bat
```

Or directly:

```bat
python main.py
```

The app starts in the system tray. Right-click the tray icon to access the menu.

## Usage

### Saving a layout

- **Hotkey** (`Ctrl+Alt+S`): If you have saved before, silently overwrites the last profile. If no profile exists yet, prompts for a name.
- **Tray menu → Save layout**: Always prompts for a profile name.
- **Settings → Profiles tab → Save current layout**: Prompts for a name and saves.

### Restoring a layout

- **Hotkey** (`Ctrl+Alt+R`): Restores the last saved profile.
- **Tray menu → Restore layout**: Restores the last saved profile, or prompts if none set.
- **Settings → Profiles tab**: Select a profile and click Restore.

### Managing profiles

Open **Settings** from the tray menu. The **Profiles** tab lets you:
- Save, restore, rename, and delete profiles

### Configuring hotkeys

Open **Settings → Hotkeys** tab. Enter any key combination supported by the [`keyboard`](https://github.com/boppreh/keyboard) library (e.g. `ctrl+shift+s`).

## Browser Tab Capture

To capture browser tabs, you must launch Chrome and/or Edge with remote debugging enabled.

**Chrome** — create a shortcut with target:
```
chrome.exe --remote-debugging-port=9222
```

**Edge** — create a shortcut with target:
```
msedge.exe --remote-debugging-port=9223
```

The default ports (9222/9223) can be changed in **Settings → Browser Setup**.

> **Note:** Launch the browser from this shortcut *before* saving a layout. If the browser isn't running in debug mode, tabs are silently omitted from the saved profile.

## Data Storage

Profiles and config are stored in:
```
%APPDATA%\ScreenSetupSaver\
  profiles\     ← saved layouts (JSON)
  config.json   ← hotkeys and port settings
  app.log       ← application log
```

## Running Tests

```bat
pytest tests/ -v
```

## Project Structure

```
main.py          Entry point
tray.py          System tray icon and menu
settings_ui.py   Settings window (tkinter)
profiles.py      Profile and config persistence
capture.py       Window layout capture
browser.py       Browser tab capture (CDP)
restore.py       Profile restoration
hotkeys.py       Global hotkey management
assets/          Icon assets
tests/           Test suite
```
