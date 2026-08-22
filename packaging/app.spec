# PyInstaller spec — one self-contained executable per platform.
#
# Build via packaging/build.py, which runs `npm run build` first so the
# bundled UI is never stale. PyInstaller cannot cross-compile: Windows must
# be built on Windows and Linux on Linux (see .github/workflows/release.yml).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH)
ROOT = SPEC_DIR.parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"

if not (FRONTEND_DIST / "index.html").is_file():
    raise SystemExit(
        "frontend/dist is missing or unbuilt — run `npm run build` in frontend/ "
        "first, or use packaging/build.py which does it for you."
    )

# The UI is served from disk at runtime by app/paths.py, which looks for
# <bundle root>/frontend/dist. Keep that layout inside the bundle.
datas = [(str(FRONTEND_DIST), "frontend/dist")]

# uvicorn and the app's routers are reached dynamically (uvicorn by import
# string, routers via include_router), so static analysis misses them.
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("app")
    + ["anyio", "click", "h11", "websockets", "watchfiles"]
)

_icon_candidate = SPEC_DIR / "icon.ico"
_WIN_ICON = _icon_candidate if (sys.platform == "win32" and _icon_candidate.is_file()) else None

block_cipher = None

a = Analysis(
    [str(BACKEND / "app" / "desktop.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Trim the heavy scientific/GUI stack PyInstaller otherwise drags in.
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas", "PIL", "pytest",
        # uvicorn[standard] pulls uvloop (~15 MB). A single-user loopback
        # server does not need it; uvicorn falls back to asyncio cleanly.
        "uvloop",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


def _strip_gtk_bloat(datas):
    """Drop GTK icon/theme data the app can never display.

    PyInstaller's gi hook collects every installed GTK icon theme and
    theme engine — Yaru, Adwaita, HighContrast and friends — which on a
    stock Ubuntu comes to ~170 MB. This app draws its entire interface
    inside a WebView; the only GTK surface is the window frame, which the
    compositor decorates. `hicolor` is kept because GTK expects the
    fallback theme's index to exist.
    """
    keep = []
    dropped = 0
    for entry in datas:
        dest = entry[0].replace("\\", "/")
        is_icon_theme = dest.startswith("share/icons/") and not dest.startswith("share/icons/hicolor/")
        is_gtk_theme = dest.startswith("share/themes/")
        if is_icon_theme or is_gtk_theme:
            dropped += 1
            continue
        keep.append(entry)
    print(f"[app.spec] dropped {dropped} GTK icon/theme data files")
    return keep


a.datas = _strip_gtk_bloat(a.datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="android-backup-manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # GUI app: no console window on Windows. On Linux this flag is ignored,
    # and stderr still reaches the terminal when launched from one.
    console=False,
    # Only when the file is actually there. PyInstaller raises FileNotFoundError
    # for a named-but-missing icon, and there is no icon.ico in the repo yet.
    icon=str(_WIN_ICON) if _WIN_ICON else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="android-backup-manager",
)
