"""System tray icon and menu for Screen Setup Saver."""

from __future__ import annotations

import logging
import os
import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger(__name__)

_ICON_SIZE = 64
_BG_COLOR   = (30, 136, 229)   # Material Blue 600
_TEXT_COLOR = (255, 255, 255)


def _make_icon_image() -> Image.Image:
    """Generate a simple icon: blue square with white 'S'."""
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), _BG_COLOR)
    draw = ImageDraw.Draw(img)
    # Draw a white 'S' centred in the icon
    draw.text((_ICON_SIZE // 2, _ICON_SIZE // 2), "S", fill=_TEXT_COLOR, anchor="mm")
    return img


def _load_icon_image(assets_dir: str = "assets") -> Image.Image:
    """Try to load assets/icon.png; fall back to generated image."""
    path = os.path.join(assets_dir, "icon.png")
    if os.path.isfile(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return _make_icon_image()


class TrayApp:
    """Manages the pystray icon and menu.

    Callbacks (all called from tray thread — use thread-safe mechanisms if
    they touch tkinter):
        on_save()       — save current layout
        on_restore()    — restore last profile
        on_settings()   — show settings window
        on_quit()       — shut down app
    """

    def __init__(
        self,
        on_save: Callable[[], None],
        on_restore: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_save     = on_save
        self._on_restore  = on_restore
        self._on_settings = on_settings
        self._on_quit     = on_quit
        self._icon: pystray.Icon | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the tray icon in a daemon thread."""
        icon_img = _load_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Save layout",    lambda icon, item: self._on_save()),
            pystray.MenuItem("Restore layout", lambda icon, item: self._on_restore()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings",       lambda icon, item: self._on_settings()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",           lambda icon, item: self._on_quit()),
        )
        self._icon = pystray.Icon(
            name="ScreenSetupSaver",
            icon=icon_img,
            title="Screen Setup Saver",
            menu=menu,
        )
        t = threading.Thread(target=self._icon.run_detached, daemon=True)
        t.start()
        log.info("Tray icon started")

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as exc:
                log.warning("Error stopping tray icon: %s", exc)
            self._icon = None
            log.info("Tray icon stopped")

    def notify(self, title: str, message: str) -> None:
        """Show a system tray notification balloon."""
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception as exc:
                log.debug("Notification failed: %s", exc)

