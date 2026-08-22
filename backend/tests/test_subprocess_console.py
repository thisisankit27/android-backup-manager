"""Every adb call must run without flashing a console window on Windows.

The heavy operations invoke adb once per file, so a regression here is not
cosmetic: it puts a console window on screen for every file in the backup.
These tests pin both platform branches so the Windows fix cannot be undone,
and so it cannot start leaking Windows-only flags onto Linux or macOS.
"""
import subprocess
import types

import pytest

from app.adb import real_client


@pytest.fixture
def fake_win32(monkeypatch):
    """Pretend to be Windows, including the Windows-only subprocess API.

    STARTUPINFO and the flag constants genuinely do not exist off Windows,
    so exercising that branch anywhere else means supplying them.
    """
    monkeypatch.setattr(real_client.sys, "platform", "win32")

    class FakeStartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = None

    monkeypatch.setattr(subprocess, "STARTUPINFO", FakeStartupInfo, raising=False)
    monkeypatch.setattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001, raising=False)
    monkeypatch.setattr(subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)


def test_windows_suppresses_the_console_window(fake_win32):
    kwargs = real_client._hidden_console_kwargs()

    assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW
    startupinfo = kwargs["startupinfo"]
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == subprocess.SW_HIDE


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_other_platforms_pass_no_windows_only_flags(monkeypatch, platform):
    """creationflags/startupinfo are Windows-only; passing them elsewhere
    raises, so the branch has to stay genuinely empty."""
    monkeypatch.setattr(real_client.sys, "platform", platform)
    assert real_client._hidden_console_kwargs() == {}


def test_run_forwards_the_kwargs_to_subprocess(monkeypatch, fake_win32):
    """The flags are worthless unless _run actually applies them, and _run is
    the single choke point every adb call goes through."""
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    real_client._run(["adb", "devices"])

    assert seen["creationflags"] & subprocess.CREATE_NO_WINDOW
    assert seen["startupinfo"] is not None
    # The behaviour the rest of the code depends on must survive the change.
    assert seen["capture_output"] is True
    assert seen["text"] is True


def test_run_on_linux_keeps_the_previous_call_shape(monkeypatch):
    monkeypatch.setattr(real_client.sys, "platform", "linux")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    real_client._run(["adb", "devices"])

    assert "creationflags" not in seen
    assert "startupinfo" not in seen
    assert seen["capture_output"] is True
