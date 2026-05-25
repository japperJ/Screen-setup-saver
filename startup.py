"""Windows startup registration helpers (current user, Task Scheduler)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


TASK_NAME = "ScreenSetupSaver"


def current_launch_command() -> str:
    """Return quoted command used by startup task."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_script = Path(__file__).with_name("main.py")
    return f'"{sys.executable}" "{main_script}"'


def startup_enabled() -> bool:
    """Return True if startup task exists."""
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def enable_startup(command: str | None = None) -> None:
    """Create/update startup task for current user logon."""
    launch_command = command or current_launch_command()
    subprocess.run(
        [
            "schtasks",
            "/Create",
            "/F",
            "/SC",
            "ONLOGON",
            "/TN",
            TASK_NAME,
            "/TR",
            launch_command,
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def disable_startup() -> None:
    """Delete startup task. Missing task is treated as already-disabled."""
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").lower()
        if "cannot find the file specified" in stderr:
            return
        raise
