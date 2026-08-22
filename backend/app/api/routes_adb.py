"""Endpoints for inspecting and installing the adb prerequisite.

Kept separate from /api/device because these must work precisely when adb
is missing — the device routes cannot answer anything at all in that state.
"""
from fastapi import APIRouter

from app.adb.locate import (
    ENV_OVERRIDE,
    adb_source,
    download_url,
    find_adb,
    install_hint,
    install_platform_tools,
)
from app.api.jobs import jobs

router = APIRouter(prefix="/api/adb", tags=["adb"])


@router.get("/status")
def adb_status():
    """Whether adb is available, where it came from, and how to get it.

    Never raises when adb is missing: "missing" is the answer, and the UI
    needs it to render setup instructions.
    """
    path = find_adb()
    return {
        "found": path is not None,
        "path": path,
        "source": adb_source(),
        "hint": None if path else install_hint(),
        "download_url": download_url(),
        "env_override": ENV_OVERRIDE,
    }


@router.post("/install")
def install_adb():
    """Fetch Google's official platform-tools into the app data directory.

    Explicitly user-initiated. Runs as a job so the UI can show progress on
    a slow connection instead of appearing to hang.
    """
    def task(emit):
        path = install_platform_tools(emit)
        return {"path": path}

    return {"job_id": jobs.start("adb_install", task)}
