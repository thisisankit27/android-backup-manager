"""Local, filesystem-backed persistence.

Two kinds of storage, deliberately kept separate:

1. Working state (discoveries, selection manifests) — lives under
   ~/.android-backup-manager/state/, entirely outside any git repo. These
   are inputs to a backup, not its audit trail.

2. Per-backup audit material (manifest.json/csv, deletion previews,
   deletion/backup reports) — lives inside the timestamped backup directory
   itself, under <backup_dir>/_audit/, exactly like the proven CLI workflow.
   This keeps a backup fully self-contained and portable.

A lightweight history index (state/history.json) records pointers to both,
for the History screen.
"""
import datetime
import json
import uuid
from dataclasses import asdict
from pathlib import Path

from app.config import APP_DATA_DIR
from app.models import BackupManifest, DeletionPreview, DiscoveryResult, ManifestFileEntry, SelectionManifest
from app.serialization import discovery_from_dict, discovery_to_dict, selection_from_dict, selection_to_dict

STATE_DIR = APP_DATA_DIR / "state"
DISCOVERIES_DIR = STATE_DIR / "discoveries"
SELECTIONS_DIR = STATE_DIR / "selections"
HISTORY_PATH = STATE_DIR / "history.json"


def _ensure_dirs() -> None:
    DISCOVERIES_DIR.mkdir(parents=True, exist_ok=True)
    SELECTIONS_DIR.mkdir(parents=True, exist_ok=True)


def new_id(prefix: str) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:6]}"


def save_discovery(result: DiscoveryResult) -> str:
    _ensure_dirs()
    disc_id = new_id("disc")
    (DISCOVERIES_DIR / f"{disc_id}.json").write_text(json.dumps(discovery_to_dict(result), indent=2))
    record_history_event({
        "type": "discovery", "id": disc_id, "timestamp": result.generated_at,
        "device_serial": result.device_serial,
        "categories": len(result.categories),
        "files": sum(c.file_count for c in result.categories),
    })
    return disc_id


def load_discovery(disc_id: str) -> DiscoveryResult:
    path = DISCOVERIES_DIR / f"{disc_id}.json"
    return discovery_from_dict(json.loads(path.read_text()))


def save_selection(selection: SelectionManifest) -> str:
    """Selection manifests are write-once: freezing again always produces a
    new id, never overwrites a prior selection."""
    _ensure_dirs()
    path = SELECTIONS_DIR / f"{selection.id}.json"
    if path.exists():
        raise FileExistsError(f"selection manifest {selection.id} already exists — refusing to overwrite")
    path.write_text(json.dumps(selection_to_dict(selection), indent=2))
    included = selection.included()
    record_history_event({
        "type": "selection", "id": selection.id, "timestamp": selection.created_at,
        "device_serial": selection.device_serial,
        "included_files": len(included), "included_size": sum(e.size for e in included),
    })
    return selection.id


def load_selection(selection_id: str) -> SelectionManifest:
    path = SELECTIONS_DIR / f"{selection_id}.json"
    return selection_from_dict(json.loads(path.read_text()))


def record_history_event(event: dict) -> None:
    _ensure_dirs()
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text())
        except json.JSONDecodeError:
            history = []
    event = {**event, "recorded_at": datetime.datetime.now().isoformat(timespec="seconds")}
    history.append(event)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text())
    except json.JSONDecodeError:
        return []


# ---- per-backup audit material (lives inside the backup dir, not here) ----

def make_backup_dir(parent: Path) -> tuple[Path, str]:
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    candidate = parent / f"Android_Backup_{ts}"
    n = 2
    while candidate.exists():
        candidate = parent / f"Android_Backup_{ts}-{n}"
        n += 1
    candidate.mkdir(parents=True, exist_ok=False)
    (candidate / "_audit").mkdir(exist_ok=True)
    return candidate, ts


def write_backup_manifest(manifest: BackupManifest) -> Path:
    audit_dir = Path(manifest.backup_dir) / "_audit"
    audit_dir.mkdir(exist_ok=True)
    entries = [asdict(e) for e in manifest.entries]
    json_path = audit_dir / "manifest.json"
    json_path.write_text(json.dumps(entries, indent=2))

    import csv
    fields = list(ManifestFileEntry.__dataclass_fields__.keys())
    with open(audit_dir / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in entries:
            w.writerow(e)

    import hashlib
    h = hashlib.sha256(json_path.read_bytes()).hexdigest()
    (audit_dir / "manifest.sha256").write_text(f"{h}  manifest.json\n")

    record_history_event({
        "type": "backup", "id": manifest.id, "timestamp": manifest.created_at,
        "device_serial": manifest.device_serial, "backup_dir": manifest.backup_dir,
        "files": len(manifest.entries),
        "verified": sum(1 for e in manifest.entries if e.verification_status == "verified"),
        "size": sum(e.backup_size or 0 for e in manifest.entries if e.verification_status == "verified"),
    })
    return json_path


def load_backup_manifest_entries(backup_dir: str) -> list[dict]:
    path = Path(backup_dir) / "_audit" / "manifest.json"
    return json.loads(path.read_text())


def write_deletion_preview(preview: DeletionPreview, backup_dir: str) -> Path:
    audit_dir = Path(backup_dir) / "_audit"
    audit_dir.mkdir(exist_ok=True)
    path = audit_dir / f"deletion_preview_{preview.id}.json"
    if path.exists():
        raise FileExistsError("deletion preview file already exists — refusing to overwrite")
    data = {
        "id": preview.id, "created_at": preview.created_at,
        "backup_manifest_id": preview.backup_manifest_id, "device_serial": preview.device_serial,
        "eligible": [asdict(c) for c in preview.eligible],
        "skipped": [asdict(s) for s in preview.skipped],
        "crypt14_inventory": preview.crypt14_inventory,
    }
    path.write_text(json.dumps(data, indent=2))
    record_history_event({
        "type": "deletion_preview", "id": preview.id, "timestamp": preview.created_at,
        "device_serial": preview.device_serial, "backup_dir": backup_dir,
        "eligible": len(preview.eligible), "skipped": len(preview.skipped),
        "eligible_size": sum(c.size for c in preview.eligible),
    })
    return path


def load_deletion_preview(backup_dir: str, preview_id: str) -> dict:
    path = Path(backup_dir) / "_audit" / f"deletion_preview_{preview_id}.json"
    return json.loads(path.read_text())


def append_deletion_log(rows: list[dict]) -> None:
    import csv
    _ensure_dirs()
    log_path = STATE_DIR / "deletion_log.csv"
    file_exists = log_path.exists()
    fields = ["timestamp", "original_path", "filename", "original_sha256", "current_sha256",
              "backup_path", "deletion_result", "error_message"]
    with open(log_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            w.writeheader()
        for row in rows:
            w.writerow(row)


def write_deletion_report(backup_dir: str, report_id: str, summary: dict) -> Path:
    audit_dir = Path(backup_dir) / "_audit"
    path = audit_dir / f"deletion_report_{report_id}.json"
    path.write_text(json.dumps(summary, indent=2))
    record_history_event({
        "type": "deletion", "id": report_id, "timestamp": summary.get("generated_at"),
        "device_serial": summary.get("device_serial"), "backup_dir": backup_dir,
        "deleted": summary.get("deleted_count"), "skipped": summary.get("skipped_count"),
        "deleted_size": summary.get("deleted_size"),
        "aborted_reason": summary.get("aborted_reason"),
    })
    return path
