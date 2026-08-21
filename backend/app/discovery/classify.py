"""Classification rules: which top-level Android directories map to which
category, and per-file rules (trash detection, .crypt14 current/historical).

Kept data-driven and generic on purpose — this app is meant to work against
more than one phone, so it does not hardcode any single device's personal
folder names (e.g. a user-created vlog-footage folder). Anything under the
storage root that isn't a recognized system directory is discovered as its
own "custom" category, named after itself.
"""
import os
import re

from app.models import Crypt14Kind

STORAGE_ROOT = "/storage/emulated/0"

# Top-level directories with OS/vendor-defined meaning. Anything else found
# directly under STORAGE_ROOT is treated as a user-created folder and
# discovered generically (see scanner.discover_custom_top_level_dirs).
KNOWN_TOP_LEVEL_DIRS = {
    "Android", "DCIM", "Pictures", "Movies", "Download", "Documents",
    "Music", "Alarms", "Notifications", "Podcasts", "Ringtones",
    "Audiobooks", "LOST.DIR",
}

# Subfolders that are disposable/cache by construction, wherever they appear.
DISPOSABLE_DIRNAMES = {".thumbnails", ".trashed"}

WHATSAPP_MEDIA_ROOT = f"{STORAGE_ROOT}/Android/media/com.whatsapp/WhatsApp/Media"
WHATSAPP_DATABASES_ROOT = f"{STORAGE_ROOT}/Android/media/com.whatsapp/WhatsApp/Databases"
WHATSAPP_BACKUPS_ROOT = f"{STORAGE_ROOT}/Android/media/com.whatsapp/WhatsApp/Backups"

# WhatsApp Media subfolder -> (report_group, default_include)
WHATSAPP_MEDIA_SUBFOLDERS: dict[str, tuple[str, bool]] = {
    "WhatsApp Images": ("WhatsApp", True),
    "WhatsApp Video": ("WhatsApp", True),
    "WhatsApp Audio": ("WhatsApp", True),
    "WhatsApp Voice Notes": ("WhatsApp", True),
    "WhatsApp Video Notes": ("WhatsApp", True),
    "WhatsApp Documents": ("WhatsApp", True),
    "WhatsApp Animated Gifs": ("Disposable", False),
    "WhatsApp Stickers": ("Disposable", False),
    "WhatsApp Profile Photos": ("WhatsApp", True),
    "WallPaper": ("Disposable", False),
    ".Statuses": ("Disposable", False),
}

_TRASHED_RE = re.compile(r"^\.trashed-", re.IGNORECASE)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def is_trashed(filename: str) -> bool:
    return bool(_TRASHED_RE.match(filename))


def classify_crypt14(filename: str) -> Crypt14Kind | None:
    if not filename.lower().endswith(".crypt14") and not filename.lower().endswith(".crypt15"):
        return None
    return Crypt14Kind.HISTORICAL if _DATE_RE.search(filename) else Crypt14Kind.CURRENT


def extension_of(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()
