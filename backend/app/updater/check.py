"""Is there a newer release than the one running?

Everything here is best-effort by design. Offline, rate-limited, no
releases published yet, a tag nobody can parse — each of those is an
ordinary outcome, not an error the user should be shown. The one thing
this must never do is fail loudly or block startup: it is a courtesy, and
the app works perfectly without it.
"""
import json
import platform
import sys
import time

from app.config import APP_DATA_DIR, load_settings
from app.updater import versions
from app.updater.net import UnsafeUrlError, fetch
from app.version import VERSION, is_release_build

REPO = "thisisankit27/android-backup-manager"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"

_API_HOSTS = ("api.github.com",)

CACHE_PATH = APP_DATA_DIR / "update-check.json"

#: Once a day is plenty for a tool people open occasionally, and stays far
#: inside GitHub's 60-requests-an-hour unauthenticated limit.
CHECK_INTERVAL = 24 * 60 * 60
#: A failure is remembered too, so a machine with no connection retries
#: hourly rather than on every single launch.
ERROR_RETRY_INTERVAL = 60 * 60

#: The .deb filename carries a Debian architecture, not uname's.
_DEB_ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}


def asset_suffix() -> str | None:
    """The tail of the release asset filename built for this platform."""
    if sys.platform == "win32":
        return ".exe"
    if sys.platform.startswith("linux"):
        arch = _DEB_ARCH.get(platform.machine().lower())
        return f"_{arch}.deb" if arch else None
    # No macOS build is produced yet; saying so beats offering a Linux one.
    return None


def pick_asset(assets: list[dict]) -> dict | None:
    suffix = asset_suffix()
    if suffix is None:
        return None
    for asset in assets:
        if str(asset.get("name", "")).endswith(suffix):
            return asset
    return None


def _fetch_latest() -> dict:
    """The latest published release, reduced to what the UI needs."""
    payload = json.loads(
        fetch(LATEST_URL, _API_HOSTS, timeout=10, accept="application/vnd.github+json")
    )
    tag = str(payload.get("tag_name") or "")
    assets = payload.get("assets") or []
    asset = pick_asset(assets)

    return {
        "version": tag.lstrip("vV"),
        "tag": tag,
        "notes": payload.get("body") or "",
        "published_at": payload.get("published_at"),
        "html_url": payload.get("html_url") or RELEASES_PAGE,
        "asset": None
        if asset is None
        else {
            "name": asset.get("name"),
            "url": asset.get("browser_download_url"),
            "size": asset.get("size"),
        },
        # Every asset name, so phase 2 can find SHA256SUMS without a
        # second round trip to the API.
        "asset_names": [a.get("name") for a in assets],
        "assets": [
            {"name": a.get("name"), "url": a.get("browser_download_url"), "size": a.get("size")}
            for a in assets
        ],
    }


def _read_cache() -> dict | None:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(entry: dict) -> None:
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(entry, indent=2))
    except OSError:
        # A cache that cannot be written costs an extra request later. It
        # is not worth failing the check over.
        pass


def _cache_is_fresh(entry: dict, now: float) -> bool:
    age = now - float(entry.get("checked_at") or 0)
    interval = ERROR_RETRY_INTERVAL if entry.get("error") else CHECK_INTERVAL
    return 0 <= age < interval


def check(force: bool = False) -> dict:
    """Report what is available, without ever raising.

    Returns the full picture rather than a bare answer, because the caller
    has to render three different states from it: not-yet-asked, asked-and-
    declined, and enabled.
    """
    settings = load_settings()
    enabled = settings.update_check_enabled

    result = {
        "current_version": VERSION,
        "is_release_build": is_release_build(),
        # Tri-state, flattened for the UI: has the user been asked, and
        # what did they say.
        "asked": enabled is not None,
        "enabled": enabled is True,
        "supported": asset_suffix() is not None,
        "available": False,
        "latest": None,
        "dismissed": False,
        "checked_at": None,
        "error": None,
        "releases_url": RELEASES_PAGE,
    }

    # Until the user has said yes, nothing leaves this process.
    if enabled is not True:
        return result

    now = time.time()
    cached = _read_cache()
    if cached and not force and _cache_is_fresh(cached, now):
        entry = cached
    else:
        try:
            entry = {"checked_at": now, "release": _fetch_latest(), "error": None}
        except UnsafeUrlError:
            # Not a network hiccup — something is wrong with where we are
            # pointed. Do not cache it as a normal failure.
            raise
        except Exception as e:  # noqa: BLE001 — offline is the common case
            entry = {"checked_at": now, "release": None, "error": str(e)}
        _write_cache(entry)

    result["checked_at"] = entry.get("checked_at")
    result["error"] = entry.get("error")

    release = entry.get("release")
    if not release or not release.get("version"):
        return result

    result["latest"] = release
    result["dismissed"] = settings.update_dismissed_version == release["version"]

    # A source checkout has no version to compare and no installed copy to
    # replace, so it is told what exists but never offered an update.
    if not is_release_build():
        return result

    result["available"] = versions.is_newer(release["version"], VERSION)
    return result
