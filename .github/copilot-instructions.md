# Copilot Instructions — Screen Setup Saver

## Project summary

Windows 11 tray app that saves and restores desktop layouts:
- open windows, titles, executables, positions, sizes, and window state
- browser tabs for Chrome and Edge when remote debugging is enabled
- named profiles stored under `%APPDATA%\ScreenSetupSaver\`
- configurable global hotkeys and a small tkinter settings window

## Commands

- Install dependencies: `pip install -r requirements.txt`
- Run the app: `.\run.bat`
- Run directly: `python main.py`
- Run tests: `pytest tests/ -v`
- Run one test file: `pytest tests/test_restore.py -v`

## Architecture

- `main.py` wires together tray, hotkeys, settings, capture, browser capture, and restore.
- `tray.py` owns the system tray menu and notifications.
- `settings_ui.py` owns the tkinter settings window.
- `capture.py` enumerates visible windows and records layout metadata.
- `browser.py` captures tabs from Chrome/Edge via CDP.
- `restore.py` relaunches apps when needed, reuses already-open windows, and reapplies placement.
- `profiles.py` persists profiles/config in `%APPDATA%`.
- `hotkeys.py` registers and replaces global hotkeys.

## Key conventions

- Use PowerShell-friendly script paths in docs and examples: `.\run.bat`, not `run.bat`.
- When restoring, check for already-open app windows first and reposition them instead of launching duplicates.
- Capture should skip minimized windows; the saved layout represents the active visible desktop, not minimized clutter.
- Window rectangles are screen coordinates from `GetWindowRect`; preserve negative coordinates and do not mix them with `GetWindowPlacement` workspace values.
- Browser capture is optional at save time; if Chrome or Edge is not running with the expected debug port, window capture still succeeds.
- Keep profile data compact and JSON-friendly; tests rely on the current `windows` and `browser_tabs` structure.

## Browser setup

- Chrome debug port: `9222`
- Edge debug port: `9223`
- Saved browser tabs should be restored per browser, not merged into one generic browser bucket.

## Testing notes

- Prefer focused tests in `tests/test_*.py` when touching one module.
- The test suite uses mocks heavily; keep behavior deterministic and avoid adding real OS or browser dependencies to tests.
