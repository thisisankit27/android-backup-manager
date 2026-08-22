"""Locating the `adb` executable.

A packaged app cannot assume `adb` is on PATH the way a developer machine
can. We deliberately do NOT ship a copy: the Android SDK Platform-Tools
licence makes redistribution murky, and a bundled adb goes stale. Instead
we look in the places it realistically lives and, failing that, raise an
error the UI can turn into actionable instructions.

Resolution order:

1. ``ANDROID_BACKUP_MANAGER_ADB`` — explicit override, wins over everything.
2. ``adb`` on PATH — covers most developer machines and any user who
   installed platform-tools through their package manager.
3. A copy previously fetched into the app data directory by first-run setup.
"""
import os
import shutil
import sys
from pathlib import Path

from app.adb.errors import AdbError
from app.config import APP_DATA_DIR

ENV_OVERRIDE = "ANDROID_BACKUP_MANAGER_ADB"

_EXE = "adb.exe" if sys.platform == "win32" else "adb"

#: Where first-run setup unpacks the official platform-tools download.
MANAGED_ADB = APP_DATA_DIR / "platform-tools" / _EXE

INSTALL_HINT = (
    "adb (Android Platform Tools) could not be found.\n\n"
    "Install it with your package manager (e.g. `sudo apt install "
    "android-tools-adb` on Ubuntu), or download the official platform-tools "
    "from https://developer.android.com/tools/releases/platform-tools and "
    f"either put it on your PATH or set {ENV_OVERRIDE} to its full path."
)


def find_adb() -> str | None:
    """Return a usable adb path, or None if there isn't one."""
    override = os.environ.get(ENV_OVERRIDE)
    if override and Path(override).is_file():
        return override

    on_path = shutil.which("adb")
    if on_path:
        return on_path

    if MANAGED_ADB.is_file():
        return str(MANAGED_ADB)

    return None


def adb_path() -> str:
    """Return a usable adb path, or raise with instructions for the user."""
    found = find_adb()
    if found is None:
        raise AdbError(INSTALL_HINT)
    return found
