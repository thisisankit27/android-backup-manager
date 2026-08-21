"""Fresh pre-deletion verification. Manifest-driven: the only files ever
considered are the exact entries of a specific backup manifest — this
function performs NO new directory search beyond re-scanning those exact
manifest entries' parent directories to get their *current* state.

Raises AdbError if the device connection fails partway through; callers
must treat that as a hard stop (no partial/misleading preview is returned).
"""
import datetime
import os
from collections import defaultdict

from app.adb.client import AdbClient
from app.audit.store import new_id
from app.discovery.classify import classify_crypt14
from app.hashing import sha256_file
from app.models import Crypt14Kind, DeletionCandidate, DeletionPreview, SkippedCandidate

REQUIRED_FIELDS = ["source_path", "backup_path", "filename", "source_size",
                   "source_sha256", "backup_sha256", "copy_status", "verification_status"]


def _entry_complete(e: dict) -> bool:
    return all(e.get(f) not in (None, "") for f in REQUIRED_FIELDS)


def run_deletion_preview(client: AdbClient, manifest_id: str, manifest_entries: list[dict],
                          device_serial: str) -> DeletionPreview:
    by_dir: dict[str, list[dict]] = defaultdict(list)
    for e in manifest_entries:
        by_dir[os.path.dirname(e["source_path"])].append(e)

    eligible: list[DeletionCandidate] = []
    skipped: list[SkippedCandidate] = []
    crypt14_inventory: list[dict] = []

    for remote_dir, entries in sorted(by_dir.items()):
        current = client.scan_dir(remote_dir, max_depth=1)

        for e in entries:
            source_path = e["source_path"]
            filename = e["filename"]
            crypt_kind = classify_crypt14(filename)
            reason = None
            detail = ""

            if e.get("verification_status") != "verified":
                reason, detail = "other", "original backup verification was not successful for this file"
            elif not _entry_complete(e):
                reason, detail = "incomplete manifest", "one or more required manifest fields are missing"
            elif source_path not in current:
                reason, detail = "missing", "exact source path no longer exists on device"
            elif current[source_path].sha256 != e["source_sha256"]:
                reason, detail = "source hash mismatch", "current on-device content differs from what was backed up"
            elif not os.path.isfile(e["backup_path"]):
                reason, detail = "backup missing", "backup copy no longer exists at the recorded path"
            else:
                backup_hash = sha256_file(e["backup_path"])
                if backup_hash != e["backup_sha256"]:
                    reason, detail = "backup hash mismatch", "local backup file no longer matches its recorded hash"
                elif crypt_kind == Crypt14Kind.CURRENT:
                    reason, detail = "other", "current/undated WhatsApp database — protected by policy"

            if crypt_kind:
                crypt14_inventory.append({
                    "source_path": source_path, "filename": filename, "kind": crypt_kind.value,
                    "size": e.get("source_size"), "eligible": reason is None,
                    "reason": reason, "detail": detail,
                })

            if reason is None:
                eligible.append(DeletionCandidate(
                    source_path=source_path, backup_path=e["backup_path"],
                    source_sha256=e["source_sha256"], backup_sha256=e["backup_sha256"],
                    size=e.get("source_size") or 0, category=e.get("category", ""), crypt14_kind=crypt_kind,
                ))
            else:
                skipped.append(SkippedCandidate(
                    source_path=source_path, backup_path=e.get("backup_path"), reason=reason, detail=detail,
                ))

    return DeletionPreview(
        id=new_id("preview"),
        created_at=datetime.datetime.now().isoformat(timespec="seconds"),
        backup_manifest_id=manifest_id,
        device_serial=device_serial,
        eligible=eligible,
        skipped=skipped,
        crypt14_inventory=crypt14_inventory,
    )
