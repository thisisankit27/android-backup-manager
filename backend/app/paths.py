"""Runtime path resolution.

The app runs in two very different layouts:

* from source, where the repo tree is on disk and the frontend is built
  into ``frontend/dist``;
* from a PyInstaller bundle, where everything was unpacked into a
  temporary directory that PyInstaller points at with ``sys._MEIPASS``.

Everything that needs to find a file at runtime goes through here so that
difference lives in exactly one place.
"""
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_dir() -> Path:
    """Directory that bundled read-only resources were unpacked into.

    From source this is the repo root; frozen it is PyInstaller's temp
    extraction directory.
    """
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # backend/app/paths.py -> backend/app -> backend -> repo root
    return Path(__file__).resolve().parent.parent.parent


def frontend_dir() -> Path | None:
    """Built frontend to serve, or None when it hasn't been built yet.

    Frozen builds carry ``frontend/dist`` at the bundle root. From source we
    look in the repo checkout, which is empty until ``npm run build`` runs —
    in that case the caller falls back to the Vite dev server.
    """
    candidate = resource_dir() / "frontend" / "dist"
    return candidate if (candidate / "index.html").is_file() else None
