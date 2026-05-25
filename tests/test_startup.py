"""Tests for startup.py — Windows startup registration via Task Scheduler."""

from pathlib import Path
from unittest.mock import Mock, patch
import subprocess
import pytest


class TestStartupEnabled:
    def test_true_when_task_exists(self):
        import startup

        with patch("startup.subprocess.run", return_value=Mock(returncode=0)) as mock_run:
            assert startup.startup_enabled() is True

        mock_run.assert_called_once_with(
            ["schtasks", "/Query", "/TN", startup.TASK_NAME],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_false_when_task_missing(self):
        import startup

        with patch("startup.subprocess.run", return_value=Mock(returncode=1)):
            assert startup.startup_enabled() is False


class TestEnableStartup:
    def test_uses_supplied_launch_command(self):
        import startup

        with patch("startup.subprocess.run") as mock_run:
            startup.enable_startup('"C:\\Program Files\\Screen Setup Saver\\ScreenSetupSaver.exe"')

        mock_run.assert_called_once_with(
            [
                "schtasks",
                "/Create",
                "/F",
                "/SC",
                "ONLOGON",
                "/TN",
                startup.TASK_NAME,
                "/TR",
                '"C:\\Program Files\\Screen Setup Saver\\ScreenSetupSaver.exe"',
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_uses_default_launch_command_when_not_supplied(self):
        import startup

        with patch("startup.current_launch_command", return_value='"C:\\A\\ScreenSetupSaver.exe"'), \
             patch("startup.subprocess.run") as mock_run:
            startup.enable_startup()

        assert mock_run.call_args.args[0][-1] == '"C:\\A\\ScreenSetupSaver.exe"'


class TestDisableStartup:
    def test_deletes_task(self):
        import startup

        with patch("startup.subprocess.run") as mock_run:
            startup.disable_startup()

        mock_run.assert_called_once_with(
            ["schtasks", "/Delete", "/F", "/TN", startup.TASK_NAME],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_ignores_missing_task_error(self):
        import startup

        err = subprocess.CalledProcessError(
            returncode=1,
            cmd=["schtasks", "/Delete"],
            stderr="ERROR: The system cannot find the file specified.",
        )
        with patch("startup.subprocess.run", side_effect=err):
            startup.disable_startup()  # should not raise

    def test_raises_other_delete_errors(self):
        import startup

        err = subprocess.CalledProcessError(
            returncode=1,
            cmd=["schtasks", "/Delete"],
            stderr="Access is denied.",
        )
        with patch("startup.subprocess.run", side_effect=err):
            with pytest.raises(subprocess.CalledProcessError):
                startup.disable_startup()


class TestCurrentLaunchCommand:
    def test_returns_frozen_exe_when_running_frozen(self):
        import startup

        with patch.object(startup.sys, "frozen", True, create=True), \
             patch("startup.sys.executable", "C:\\Program Files\\ScreenSetupSaver\\ScreenSetupSaver.exe"):
            cmd = startup.current_launch_command()
        assert cmd == '"C:\\Program Files\\ScreenSetupSaver\\ScreenSetupSaver.exe"'

    def test_returns_python_and_main_script_when_not_frozen(self):
        import startup

        with patch.object(startup.sys, "frozen", False, create=True), \
             patch("startup.sys.executable", "C:\\Python313\\python.exe"), \
             patch("startup.Path", return_value=Path("C:\\REP\\Screen-setup-saver\\startup.py")):
            cmd = startup.current_launch_command()
        assert cmd == '"C:\\Python313\\python.exe" "C:\\REP\\Screen-setup-saver\\main.py"'
