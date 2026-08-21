"""Executes deletion for exactly the eligible entries of one already-
generated DeletionPreview. Never performs a new search. Never deletes a
directory — only individual files, each via AdbClient.verify_and_delete,
which re-checks the hash one more time at the moment of deletion and
confirms the file is actually gone afterward.

If the device connection is lost partway through, this raises AdbError;
the caller must stop immediately and treat everything already appended to
`deleted`/`log_rows` at that point as final.
"""
import datetime
import os
from collections import defaultdict
from typing import Callable

from app.adb.client import AdbClient
from app.adb.types import DeletionOutcome
from app.config import Settings
from app.models import DeletionPreview

ProgressCallback = Callable[[dict], None]


class DeletionAborted(RuntimeError):
    def __init__(self, reason: str, deleted: list[dict], skipped: list[dict], log_rows: list[dict]):
        super().__init__(reason)
        self.reason = reason
        self.deleted = deleted
        self.skipped = skipped
        self.log_rows = log_rows


def _log_row(source_path: str, filename: str, original_hash, current_hash, backup_path, result: str, error: str) -> dict:
    return {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "original_path": source_path, "filename": filename,
        "original_sha256": original_hash or "", "current_sha256": current_hash or "",
        "backup_path": backup_path or "", "deletion_result": result, "error_message": error,
    }


def execute_deletion(client: AdbClient, preview: DeletionPreview, manifest_entries_by_path: dict[str, dict],
                      settings: Settings, dry_run: bool = False, progress: ProgressCallback | None = None
                      ) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (deleted, skipped, log_rows). Raises DeletionAborted if the
    connection is lost mid-run (partial results are attached to the
    exception so callers can still persist/report what happened)."""

    def emit(event: dict):
        if progress:
            progress(event)

    protected_names = set(settings.protected_filename_patterns)

    candidates = []
    for c in preview.eligible:
        filename = os.path.basename(c.source_path)
        manifest_entry = manifest_entries_by_path.get(c.source_path)
        if filename in protected_names:
            candidates.append((c, "hard-protected filename — excluded by policy"))
        elif not manifest_entry or manifest_entry.get("source_sha256") != c.source_sha256:
            candidates.append((c, "ambiguous — preview entry does not match the verified manifest"))
        else:
            candidates.append((c, None))

    deleted: list[dict] = []
    skipped: list[dict] = []
    log_rows: list[dict] = []
    total = len(candidates)
    emit({"phase": "start", "total": total})

    for c, pre_skip in candidates:
        if pre_skip:
            skipped.append({"source_path": c.source_path, "reason": pre_skip})
            log_rows.append(_log_row(c.source_path, os.path.basename(c.source_path), c.source_sha256, None, c.backup_path, "skipped", pre_skip))

    to_process = [(c, r) for c, r in candidates if r is None]
    by_dir = defaultdict(list)
    for c, _ in to_process:
        by_dir[os.path.dirname(c.source_path)].append(c)

    done = 0
    try:
        for remote_dir, entries in sorted(by_dir.items()):
            current = client.scan_dir(remote_dir, max_depth=1)
            for c in entries:
                filename = os.path.basename(c.source_path)
                fresh = current.get(c.source_path)

                if fresh is None:
                    skipped.append({"source_path": c.source_path, "reason": "missing since preview"})
                    log_rows.append(_log_row(c.source_path, filename, c.source_sha256, None, c.backup_path, "skipped", "source file no longer present"))
                elif fresh.sha256 != c.source_sha256:
                    skipped.append({"source_path": c.source_path, "reason": "changed since preview"})
                    log_rows.append(_log_row(c.source_path, filename, c.source_sha256, fresh.sha256, c.backup_path, "skipped", "source hash changed since preview"))
                elif not os.path.isfile(c.backup_path):
                    skipped.append({"source_path": c.source_path, "reason": "backup missing"})
                    log_rows.append(_log_row(c.source_path, filename, c.source_sha256, fresh.sha256, c.backup_path, "skipped", "backup copy no longer found"))
                else:
                    result = client.verify_and_delete(c.source_path, c.source_sha256, dry_run=dry_run)
                    if result.outcome in (DeletionOutcome.DELETED, DeletionOutcome.WOULD_DELETE):
                        deleted.append({"source_path": c.source_path, "size": c.size})
                        log_rows.append(_log_row(c.source_path, filename, c.source_sha256, c.source_sha256, c.backup_path,
                                                  "would_delete" if dry_run else "deleted", ""))
                    elif result.outcome == DeletionOutcome.GONE:
                        skipped.append({"source_path": c.source_path, "reason": "disappeared at moment of deletion"})
                        log_rows.append(_log_row(c.source_path, filename, c.source_sha256, None, c.backup_path, "skipped", "file disappeared between re-check and deletion"))
                    elif result.outcome == DeletionOutcome.HASH_MISMATCH:
                        skipped.append({"source_path": c.source_path, "reason": "hash changed at moment of deletion"})
                        log_rows.append(_log_row(c.source_path, filename, c.source_sha256, result.observed_sha256, c.backup_path, "skipped", "hash changed between re-check and deletion"))
                    elif result.outcome == DeletionOutcome.STILL_EXISTS:
                        skipped.append({"source_path": c.source_path, "reason": "MANUAL REVIEW: rm reported success but file still present"})
                        log_rows.append(_log_row(c.source_path, filename, c.source_sha256, c.source_sha256, c.backup_path, "failed", "rm exited 0 but file still exists"))
                    else:
                        skipped.append({"source_path": c.source_path, "reason": f"MANUAL REVIEW: unexpected result {result.outcome}"})
                        log_rows.append(_log_row(c.source_path, filename, c.source_sha256, None, c.backup_path, "failed", f"unexpected result: {result.outcome}"))
                done += 1
                emit({"phase": "progress", "path": c.source_path, "done": done, "total": total})
    except Exception as e:
        emit({"phase": "aborted", "reason": str(e), "done": done, "total": total})
        raise DeletionAborted(str(e), deleted, skipped, log_rows) from e

    emit({"phase": "done", "done": done, "total": total})
    return deleted, skipped, log_rows
