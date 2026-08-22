"""Locating — and, when necessary, installing — the `adb` executable.

A packaged app cannot assume `adb` is on PATH the way a developer machine
can. We deliberately do NOT ship a copy: the Android SDK Platform-Tools
licence makes redistribution murky, and a bundled adb goes stale. Instead
we look in the places it realistically lives and, failing that, offer to
fetch Google's official platform-tools into the app's own data directory.

Resolution order:

1. ``ANDROID_BACKUP_MANAGER_ADB`` — explicit override, wins over everything.
2. ``adb`` on PATH — covers most developer machines and any user who
   installed platform-tools through their package manager.
3. A copy previously fetched by :func:`install_platform_tools`.
"""
import io
import os
import shutil
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path

from app.adb.errors import AdbError
from app.config import APP_DATA_DIR

ENV_OVERRIDE = "ANDROID_BACKUP_MANAGER_ADB"

_IS_WIN = sys.platform == "win32"
_EXE = "adb.exe" if _IS_WIN else "adb"

#: Where install_platform_tools() unpacks the official download.
MANAGED_DIR = APP_DATA_DIR / "platform-tools"
MANAGED_ADB = MANAGED_DIR / _EXE

#: Google's official platform-tools downloads. HTTPS, and the host is
#: asserted before anything is written to disk.
_DOWNLOADS = {
    "win32": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
    "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
}
_ALLOWED_HOST = "dl.google.com"


def _platform_key() -> str:
    if _IS_WIN:
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def download_url() -> str | None:
    return _DOWNLOADS.get(_platform_key())


def install_hint() -> str:
    """Guidance for this platform.

    Deliberately not one shared string: telling a Windows user to run
    `sudo apt install` is worse than saying nothing.
    """
    common = (
        "adb (Android Platform Tools) could not be found.\n\n"
        "You can let this app download the official platform-tools from "
        "Google, or install them yourself"
    )
    if _IS_WIN:
        return (
            f"{common}:\n"
            "  • winget install Google.PlatformTools\n"
            "  • or download from "
            "https://developer.android.com/tools/releases/platform-tools "
            "and add the folder to your PATH."
        )
    if sys.platform == "darwin":
        return f"{common}:\n  • brew install --cask android-platform-tools"
    return (
        f"{common}:\n"
        "  • sudo apt install android-tools-adb   (Debian/Ubuntu)\n"
        "  • sudo dnf install android-tools       (Fedora)"
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


def adb_source() -> str | None:
    """Which of the three resolution routes produced the current adb."""
    override = os.environ.get(ENV_OVERRIDE)
    if override and Path(override).is_file():
        return "override"
    if shutil.which("adb"):
        return "path"
    if MANAGED_ADB.is_file():
        return "managed"
    return None


def adb_path() -> str:
    """Return a usable adb path, or raise with instructions for the user."""
    found = find_adb()
    if found is None:
        raise AdbError(install_hint())
    return found


def install_platform_tools(emit=None) -> str:
    """Download Google's official platform-tools and return the adb path.

    User-initiated only — never called implicitly on startup. Downloading
    ~10 MB of executables from the internet is something the user should be
    asked about, not something that quietly happens behind a status bar.
    """
    def progress(phase: str, **extra):
        if emit:
            emit({"phase": phase, **extra})

    url = download_url()
    if url is None:
        raise AdbError(f"No official platform-tools build for this platform ({sys.platform}).")

    # The URL is a constant above, but assert the host anyway so that a
    # future edit can't silently turn this into a fetch-and-execute from
    # somewhere else.
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
        raise AdbError(f"refusing to download platform-tools from {url!r}")

    progress("downloading", url=url)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
    except Exception as e:  # noqa: BLE001 — reported to the user as-is
        raise AdbError(f"Could not download platform-tools: {e}") from e

    progress("extracting", bytes=len(payload))

    staging = APP_DATA_DIR / "platform-tools.tmp"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            for member in zf.namelist():
                # Guard against zip-slip: no absolute paths, no traversal.
                target = (staging / member).resolve()
                if not str(target).startswith(str(staging.resolve())):
                    raise AdbError(f"unsafe path in platform-tools archive: {member!r}")
            zf.extractall(staging)
    except zipfile.BadZipFile as e:
        shutil.rmtree(staging, ignore_errors=True)
        raise AdbError("Downloaded platform-tools archive was not a valid zip.") from e

    # The archive contains a single top-level platform-tools/ directory.
    extracted = staging / "platform-tools"
    if not (extracted / _EXE).is_file():
        shutil.rmtree(staging, ignore_errors=True)
        raise AdbError("Downloaded archive did not contain an adb executable.")

    if MANAGED_DIR.exists():
        shutil.rmtree(MANAGED_DIR, ignore_errors=True)
    MANAGED_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(extracted), str(MANAGED_DIR))
    shutil.rmtree(staging, ignore_errors=True)

    if not _IS_WIN:
        # zipfile drops the executable bit.
        for f in MANAGED_DIR.iterdir():
            if f.is_file():
                f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    progress("done", path=str(MANAGED_ADB))
    return str(MANAGED_ADB)
