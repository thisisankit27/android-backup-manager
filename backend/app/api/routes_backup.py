from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.adb.real_client import RealAdbClient, check_single_device
from app.api.jobs import jobs
from app.api.schemas import FreezeSelectionRequest, StartBackupRequest
from app.audit.store import load_discovery, load_selection, make_backup_dir, new_id, write_backup_manifest
from app.backup.engine import run_backup
from app.config import load_settings
from app.manifest.duplicates import find_duplicate_groups
from app.reports.render import render_backup_report
from app.selection.freezer import freeze_selection
from app.serialization import selection_to_dict

router = APIRouter(prefix="/api", tags=["backup"])


@router.post("/selection/freeze")
def freeze(req: FreezeSelectionRequest):
    try:
        discovery = load_discovery(req.discovery_id)
    except FileNotFoundError:
        raise HTTPException(404, "discovery not found")
    selection = freeze_selection(discovery, req.overrides)
    included = selection.included()
    return {
        "selection_id": selection.id,
        "included_files": len(included),
        "included_size": sum(e.size for e in included),
        "excluded_files": len(selection.entries) - len(included),
    }


@router.get("/selection/{selection_id}")
def get_selection(selection_id: str):
    try:
        selection = load_selection(selection_id)
    except FileNotFoundError:
        raise HTTPException(404, "selection not found")
    return selection_to_dict(selection)


@router.post("/backup/start")
def start_backup(req: StartBackupRequest):
    serial = check_single_device()
    try:
        selection = load_selection(req.selection_id)
    except FileNotFoundError:
        raise HTTPException(404, "selection not found")
    if selection.device_serial != serial:
        raise HTTPException(409, f"connected device ({serial}) does not match the device this selection was made for ({selection.device_serial})")

    settings = load_settings()
    dest_parent = Path(req.dest_parent or settings.default_backup_parent).expanduser()
    dest_parent.mkdir(parents=True, exist_ok=True)
    backup_dir, ts = make_backup_dir(dest_parent)
    backup_id = new_id("backup")

    def task(emit):
        client = RealAdbClient(serial)
        manifest = run_backup(client, selection, backup_dir, backup_id=backup_id, progress=emit)
        manifest.backup_dir = str(backup_dir)
        write_backup_manifest(manifest)
        return {"backup_id": backup_id, "backup_dir": str(backup_dir),
                "total": len(manifest.entries),
                "verified": sum(1 for e in manifest.entries if e.verification_status == "verified")}

    job_id = jobs.start("backup", task)
    return {"job_id": job_id, "backup_dir": str(backup_dir)}


@router.get("/backup/manifest")
def get_manifest(backup_dir: str):
    from app.audit.store import load_backup_manifest_entries
    try:
        entries = load_backup_manifest_entries(backup_dir)
    except FileNotFoundError:
        raise HTTPException(404, "manifest not found for this backup directory")
    duplicates = find_duplicate_groups(entries)
    from app.audit.store import load_history
    history = load_history()
    match = next((h for h in reversed(history) if h.get("type") == "backup" and h.get("backup_dir") == backup_dir), None)
    device_serial = match["device_serial"] if match else "unknown"
    txt, html = render_backup_report(entries, device_serial, backup_dir, duplicates)
    return {"entries": entries, "duplicate_groups": duplicates, "report_txt": txt, "report_html": html}
