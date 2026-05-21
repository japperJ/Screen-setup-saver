import sys
from unittest.mock import MagicMock

# Stub out Windows-only modules so tests can import app modules on any machine
for mod in [
    "win32gui", "win32process", "win32con", "win32api", "pystray", "keyboard",
]:
    sys.modules.setdefault(mod, MagicMock())
