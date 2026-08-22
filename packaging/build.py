#!/usr/bin/env python3
"""Build the desktop bundle for the current platform.

Runs the frontend build first so the bundled UI can never be stale, then
PyInstaller. PyInstaller cannot cross-compile — run this on the platform you
are targeting.

    python packaging/build.py            # build everything
    python packaging/build.py --no-ui    # reuse the existing frontend/dist
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str], cwd: Path) -> None:
    printable = " ".join(cmd)
    print(f"\n$ {printable}   (in {cwd})", flush=True)
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(f"failed ({result.returncode}): {printable}")


def build_frontend() -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm not found on PATH — needed to build the frontend.")
    if not (FRONTEND / "node_modules").is_dir():
        run([npm, "ci"], cwd=FRONTEND)
    run([npm, "run", "build"], cwd=FRONTEND)


def build_bundle() -> None:
    # Invoked through the current interpreter so it uses this venv's
    # PyInstaller and, critically, this venv's installed dependencies.
    run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean",
            "--distpath", str(DIST),
            "--workpath", str(BUILD),
            str(PACKAGING / "app.spec"),
        ],
        cwd=ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-ui", action="store_true",
                        help="skip the frontend build and reuse frontend/dist")
    args = parser.parse_args()

    if args.no_ui:
        if not (FRONTEND / "dist" / "index.html").is_file():
            raise SystemExit("--no-ui given but frontend/dist is not built.")
        print("skipping frontend build (--no-ui)")
    else:
        build_frontend()

    build_bundle()

    out = DIST / "android-backup-manager"
    print(f"\nBuilt: {out}")
    if out.is_dir():
        size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
        print(f"Size:  {size / 1024 ** 2:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
