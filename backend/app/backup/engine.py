"""Copy + verify pipeline. Operates ONLY against the exact paths frozen in a
SelectionManifest — never a live re-query of "what's in this category now".

For each source directory that has at least one selected file, the whole
directory is pulled (efficient single adb transfer) and then any locally
pulled file that was NOT explicitly selected — an excluded sibling, a
`.trashed-*` item, anything created after the freeze — is deleted from the
LOCAL backup copy only. The Android original is never touched by this step;
`pull` is inherently read-only on the device.
"""
import datetime
import os
from collections import defaultdict
from pathlib import Path
from typing import Callable

from app.adb.client import AdbClient
from app.adb.errors import AdbError
from app.discovery.classify import STORAGE_ROOT
from app.hashing import sha256_file
from app.models import BackupManifest, FileState, ManifestFileEntry, SelectionManifest

ProgressCallback = Callable[[dict], None]


def _relative_backup_path(remote_path: str) -> str:
    if remote_path.startswith(STORAGE_ROOT + "/"):
        return remote_path[len(STORAGE_ROOT) + 1:]
    return remote_path.lstrip("/")


def run_backup(client: AdbClient, selection: SelectionManifest, backup_dir: Path,
                backup_id: str, progress: ProgressCallback | None = None) -> BackupManifest:
    included = selection.included()
    total = len(included)
    by_dir: dict[str, list] = defaultdict(list)
    for entry in included:
        by_dir[os.path.dirname(entry.path)].append(entry)

    def emit(event: dict):
        if progress:
            progress(event)

    manifest_entries: list[ManifestFileEntry] = []
    done = 0
    emit({"phase": "start", "total": total})

    for remote_dir, entries in sorted(by_dir.items()):
        emit({"phase": "scanning", "remote_dir": remote_dir})
        try:
            fresh = client.scan_dir(remote_dir, max_depth=1)
        except AdbError as e:
            for entry in entries:
                manifest_entries.append(_failed_entry(entry, backup_dir, f"remote scan failed: {e}"))
                done += 1
                emit({"phase": "error", "path": entry.path, "done": done, "total": total})
            continue

        rel_dir = _relative_backup_path(remote_dir)
        local_dest = backup_dir / rel_dir
        selected_paths = {e.path for e in entries}

        try:
            client.pull_dir(remote_dir, local_dest)
        except AdbError as e:
            for entry in entries:
                manifest_entries.append(_failed_entry(entry, backup_dir, f"pull failed: {e}"))
                done += 1
                emit({"phase": "error", "path": entry.path, "done": done, "total": total})
            continue

        # prune anything locally pulled that wasn't explicitly selected
        if local_dest.exists():
            for root, _, files in os.walk(local_dest):
                for fname in files:
                    local_file = Path(root) / fname
                    rel = str(local_file.relative_to(local_dest))
                    remote_equiv = f"{remote_dir}/{rel}"
                    if remote_equiv not in selected_paths:
                        local_file.unlink()

        for entry in entries:
            filename = os.path.basename(entry.path)
            local_file = local_dest / os.path.relpath(entry.path, remote_dir)
            fresh_meta = fresh.get(entry.path)

            if fresh_meta is None:
                manifest_entries.append(_failed_entry(entry, backup_dir, "source file no longer exists at backup time"))
                done += 1
                emit({"phase": "copied", "path": entry.path, "done": done, "total": total, "status": "failed"})
                continue

            attempts = 0
            entry_result = None
            while attempts < 2 and entry_result is None:
                attempts += 1
                if not local_file.exists():
                    if attempts < 2:
                        try:
                            client.pull(entry.path, local_file)
                        except AdbError:
                            pass
                        continue
                    entry_result = _failed_entry(entry, backup_dir, "file missing after pull and retry",
                                                  source_size=fresh_meta.size, source_sha256=fresh_meta.sha256)
                    break
                backup_hash = sha256_file(local_file)
                backup_size = local_file.stat().st_size
                if backup_hash == fresh_meta.sha256 and backup_size == fresh_meta.size:
                    entry_result = ManifestFileEntry(
                        source_path=entry.path, backup_path=str(local_file), filename=filename,
                        extension=os.path.splitext(filename)[1].lstrip(".").lower(), category=entry.category_id,
                        source_size=fresh_meta.size, backup_size=backup_size, source_mtime=fresh_meta.mtime,
                        source_sha256=fresh_meta.sha256, backup_sha256=backup_hash,
                        copy_status="success", verification_status="verified",
                    )
                elif attempts < 2:
                    try:
                        client.pull(entry.path, local_file)
                    except AdbError:
                        pass
                    continue
                else:
                    entry_result = ManifestFileEntry(
                        source_path=entry.path, backup_path=str(local_file), filename=filename,
                        extension=os.path.splitext(filename)[1].lstrip(".").lower(), category=entry.category_id,
                        source_size=fresh_meta.size, backup_size=backup_size, source_mtime=fresh_meta.mtime,
                        source_sha256=fresh_meta.sha256, backup_sha256=backup_hash,
                        copy_status="success", verification_status="verification_failed",
                        error="hash/size mismatch after retry",
                    )

            manifest_entries.append(entry_result)
            done += 1
            emit({"phase": "copied", "path": entry.path, "done": done, "total": total,
                  "status": entry_result.verification_status})

    emit({"phase": "done", "total": total, "done": done})

    return BackupManifest(
        id=backup_id,
        created_at=datetime.datetime.now().isoformat(timespec="seconds"),
        device_serial=selection.device_serial,
        backup_dir=str(backup_dir),
        selection_manifest_id=selection.id,
        entries=manifest_entries,
    )


def _failed_entry(entry, backup_dir: Path, error: str, source_size=None, source_sha256=None) -> ManifestFileEntry:
    filename = os.path.basename(entry.path)
    return ManifestFileEntry(
        source_path=entry.path, backup_path=str(backup_dir / _relative_backup_path(entry.path)),
        filename=filename, extension=os.path.splitext(filename)[1].lstrip(".").lower(),
        category=entry.category_id, source_size=source_size, backup_size=None, source_mtime=None,
        source_sha256=source_sha256, backup_sha256=None,
        copy_status="failed", verification_status="failed", error=error,
    )
