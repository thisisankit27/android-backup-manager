"""Endpoints for the update check.

Separate router from /api/config even though the preference lives in the
settings file: these are the only endpoints in the app that can cause an
outbound network request, and that is worth being able to see at a glance.
"""
from dataclasses import asdict

from fastapi import APIRouter

from app.api.schemas import UpdateDismissRequest, UpdatePreferenceRequest
from app.config import Settings, load_settings, save_settings
from app.updater.check import check

router = APIRouter(prefix="/api/update", tags=["update"])


def _save(**changes) -> Settings:
    updated = Settings(**{**asdict(load_settings()), **changes})
    save_settings(updated)
    return updated


@router.get("/check")
def update_check(force: bool = False):
    """What the latest release is, and whether it is newer than this build.

    Returns 200 in every case, including offline and rate-limited: the UI
    renders "no update" for all of them, and an update check is not
    something that should ever paint an error over the app.
    """
    return check(force=force)


@router.post("/preference")
def set_preference(req: UpdatePreferenceRequest):
    """Record the user's answer to the first-run consent prompt.

    Also backs the Options toggle. Answering at all is what moves the
    setting off None, which is what unblocks any request being made.
    """
    _save(update_check_enabled=req.enabled)
    return check()


@router.post("/dismiss")
def dismiss(req: UpdateDismissRequest):
    """Hide the banner for one specific version.

    Per-version rather than a blanket "don't show again", so the next
    release is still announced. A backup tool that nags is worse than one
    that stays quiet, but one that sits silently on a fix is worse still.
    """
    _save(update_dismissed_version=req.version)
    return check()
