import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.adb.real_client import RealAdbClient, check_single_device
from app.api.jobs import jobs
from app.api.schemas import ExecuteDeletionRequest, StartDeletionPreviewRequest
from app.audit.store import (
    append_deletion_log,
    load_backup_manifest_entries,
    load_deletion_preview,
    write_deletion_preview,
    write_deletion_report,
)
from app.config import load_settings
from app.deletion.executor import DeletionAborted, execute_deletion
from app.deletion.preview import run_deletion_preview
from app.models import Crypt14Kind, DeletionCandidate, DeletionPreview, SkippedCandidate
from app.reports.render import render_deletion_preview_report, render_deletion_report

router = APIRouter(prefix="/api/deletion", tags=["deletion"])

REQUIRED_PHRASE = "DELETE VERIFIED BACKUPS"


@router.post("/preview/start")
def start_preview(req: StartDeletionPreviewRequest):
    serial = check_single_device()
    backup_dir = req.backup_dir
    try:
        entries = load_backup_manifest_entries(backup_dir)
    except FileNotFoundError:
        raise HTTPException(404, "no verified manifest found for this backup directory")

    def task(emit):
        emit({"phase": "scanning"})
        client = RealAdbClient(serial)
        preview = run_deletion_preview(client, backup_dir, entries, serial)
        write_deletion_preview(preview, backup_dir)
        emit({"phase": "done", "eligible": len(preview.eligible), "skipped": len(preview.skipped)})
        return {"preview_id": preview.id, "eligible": len(preview.eligible), "skipped": len(preview.skipped)}

    job_id = jobs.start("deletion_preview", task)
    return {"job_id": job_id}


@router.get("/preview")
def get_preview(backup_dir: str, preview_id: str):
    try:
        data = load_deletion_preview(backup_dir, preview_id)
    except FileNotFoundError:
        raise HTTPException(404, "preview not found")
    txt, html = render_deletion_preview_report(data)
    return {**data, "report_txt": txt, "report_html": html}


@router.post("/execute")
def execute(req: ExecuteDeletionRequest):
    if req.confirmation_phrase != REQUIRED_PHRASE:
        raise HTTPException(400, f"confirmation phrase must be exactly '{REQUIRED_PHRASE}'")
    if not req.preview_acknowledged:
        raise HTTPException(400, "the deletion preview must be explicitly acknowledged before proceeding")

    serial = check_single_device()
    try:
        preview_data = load_deletion_preview(req.backup_dir, req.preview_id)
    except FileNotFoundError:
        raise HTTPException(404, "preview not found")
    try:
        manifest_entries = load_backup_manifest_entries(req.backup_dir)
    except FileNotFoundError:
        raise HTTPException(404, "manifest not found")

    manifest_by_path = {e["source_path"]: e for e in manifest_entries}
    preview = DeletionPreview(
        id=preview_data["id"], created_at=preview_data["created_at"],
        backup_manifest_id=preview_data["backup_manifest_id"], device_serial=preview_data["device_serial"],
        eligible=[DeletionCandidate(**c) if "crypt14_kind" not in c else
                  DeletionCandidate(**{**c, "crypt14_kind": Crypt14Kind(c["crypt14_kind"]) if c["crypt14_kind"] else None})
                  for c in preview_data["eligible"]],
        skipped=[SkippedCandidate(**s) for s in preview_data["skipped"]],
        crypt14_inventory=preview_data["crypt14_inventory"],
    )

    settings = load_settings()
    backup_dir = req.backup_dir
    dry_run = req.dry_run

    def task(emit):
        client = RealAdbClient(serial)
        report_id = None
        try:
            deleted, skipped, log_rows = execute_deletion(client, preview, manifest_by_path, settings,
                                                            dry_run=dry_run, progress=emit)
            if not dry_run:
                append_deletion_log(log_rows)
            summary = {
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "backup_dir": backup_dir, "device_serial": serial, "dry_run": dry_run,
                "deleted_count": len(deleted), "deleted_size": sum(d["size"] for d in deleted),
                "skipped_count": len(skipped), "skipped": skipped,
            }
        except DeletionAborted as e:
            if not dry_run:
                append_deletion_log(e.log_rows)
            summary = {
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "backup_dir": backup_dir, "device_serial": serial, "dry_run": dry_run,
                "deleted_count": len(e.deleted), "deleted_size": sum(d["size"] for d in e.deleted),
                "skipped_count": len(e.skipped), "skipped": e.skipped,
                "aborted_reason": e.reason,
            }
        if not dry_run:
            report_id = write_deletion_report(backup_dir, preview.id, summary).stem
        txt, html = render_deletion_report(summary)
        return {**summary, "report_id": report_id, "report_txt": txt, "report_html": html}

    job_id = jobs.start("deletion_execute", task)
    return {"job_id": job_id}
