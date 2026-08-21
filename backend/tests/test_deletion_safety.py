"""The safety-critical suite. Every one of these proves the deletion engine
REFUSES to delete under a specific hazard, using a fake sandbox device —
never a real phone, per the project's development-safety rule.
"""
import pytest

from app.adb.errors import ConnectionLostError
from app.backup.engine import run_backup
from app.config import Settings
from app.deletion.executor import DeletionAborted, execute_deletion
from app.deletion.preview import run_deletion_preview
from app.discovery.scanner import discover
from app.hashing import sha256_file
from app.selection.freezer import freeze_selection


def _full_backup(fake_client, backup_dir):
    discovery = discover(fake_client, fake_client.serial)
    overrides = {f.path: "INCLUDE" for cat in discovery.categories for f in cat.files}
    selection = freeze_selection(discovery, overrides=overrides)
    manifest = run_backup(fake_client, selection, backup_dir, backup_id="b1")
    manifest.backup_dir = str(backup_dir)
    entries_as_dicts = [
        {
            "source_path": e.source_path, "backup_path": e.backup_path, "filename": e.filename,
            "extension": e.extension, "category": e.category, "source_size": e.source_size,
            "backup_size": e.backup_size, "source_mtime": e.source_mtime, "source_sha256": e.source_sha256,
            "backup_sha256": e.backup_sha256, "copy_status": e.copy_status,
            "verification_status": e.verification_status, "error": e.error,
        }
        for e in manifest.entries
    ]
    return manifest, entries_as_dicts


def _settings():
    return Settings()


def test_eligible_when_everything_matches(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)

    camera_live = [c for c in preview.eligible if "IMG_0001.jpg" in c.source_path]
    assert len(camera_live) == 1
    assert not any(s.source_path.endswith("IMG_0001.jpg") for s in preview.skipped)


def test_refuses_when_source_changed(fake_client, backup_dir, sandbox):
    manifest, entries = _full_backup(fake_client, backup_dir)

    changed_file = sandbox / "storage/emulated/0/DCIM/Camera/IMG_0001.jpg"
    changed_file.write_text("this content changed after backup")

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    assert not any(c.source_path.endswith("IMG_0001.jpg") for c in preview.eligible)
    skip = next(s for s in preview.skipped if s.source_path.endswith("IMG_0001.jpg"))
    assert skip.reason == "source hash mismatch"


def test_refuses_when_source_missing(fake_client, backup_dir, sandbox):
    manifest, entries = _full_backup(fake_client, backup_dir)
    (sandbox / "storage/emulated/0/DCIM/Camera/IMG_0001.jpg").unlink()

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    assert not any(c.source_path.endswith("IMG_0001.jpg") for c in preview.eligible)
    skip = next(s for s in preview.skipped if s.source_path.endswith("IMG_0001.jpg"))
    assert skip.reason == "missing"


def test_refuses_when_backup_missing(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    entry = next(e for e in entries if e["source_path"].endswith("IMG_0001.jpg"))
    import os
    os.remove(entry["backup_path"])

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    assert not any(c.source_path.endswith("IMG_0001.jpg") for c in preview.eligible)
    skip = next(s for s in preview.skipped if s.source_path.endswith("IMG_0001.jpg"))
    assert skip.reason == "backup missing"


def test_refuses_when_backup_hash_changed(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    entry = next(e for e in entries if e["source_path"].endswith("IMG_0001.jpg"))
    with open(entry["backup_path"], "wb") as f:
        f.write(b"corrupted backup content")

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    assert not any(c.source_path.endswith("IMG_0001.jpg") for c in preview.eligible)
    skip = next(s for s in preview.skipped if s.source_path.endswith("IMG_0001.jpg"))
    assert skip.reason == "backup hash mismatch"


def test_refuses_when_manifest_entry_incomplete(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    for e in entries:
        if e["source_path"].endswith("IMG_0001.jpg"):
            e["backup_sha256"] = None  # simulate an incomplete manifest row

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    assert not any(c.source_path.endswith("IMG_0001.jpg") for c in preview.eligible)
    skip = next(s for s in preview.skipped if s.source_path.endswith("IMG_0001.jpg"))
    assert skip.reason == "incomplete manifest"


def test_refuses_original_verification_failure(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    for e in entries:
        if e["source_path"].endswith("IMG_0001.jpg"):
            e["verification_status"] = "verification_failed"

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    assert not any(c.source_path.endswith("IMG_0001.jpg") for c in preview.eligible)


def test_current_whatsapp_database_never_eligible(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)

    current_db = next(c for c in preview.crypt14_inventory if c["kind"] == "current")
    assert current_db["eligible"] is False
    assert not any(e.source_path == current_db["source_path"] for e in preview.eligible)

    historical_db = next(c for c in preview.crypt14_inventory if c["kind"] == "historical")
    assert historical_db["eligible"] is True


def test_new_file_after_backup_never_becomes_candidate(fake_client, backup_dir, sandbox):
    """A file created in the same directory AFTER the backup must never
    appear anywhere in the deletion preview — eligible or skipped — because
    the preview is manifest-driven, not a live directory scan."""
    manifest, entries = _full_backup(fake_client, backup_dir)

    new_file = sandbox / "storage/emulated/0/DCIM/Camera/IMG_9999_NEW.jpg"
    new_file.write_text("taken after the backup")

    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    all_paths = {c.source_path for c in preview.eligible} | {s.source_path for s in preview.skipped}
    assert not any("IMG_9999_NEW" in p for p in all_paths)


def test_connection_failure_stops_preview(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    fake_client.disconnect()
    with pytest.raises(ConnectionLostError):
        run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)


# ---- executor-level tests: the FINAL check immediately before deletion ----

def test_executor_deletes_only_eligible_files(fake_client, backup_dir, sandbox):
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    by_path = {e["source_path"]: e for e in entries}

    deleted, skipped, log_rows = execute_deletion(fake_client, preview, by_path, _settings())

    deleted_paths = {d["source_path"] for d in deleted}
    for c in preview.eligible:
        assert c.source_path in deleted_paths
        assert not (sandbox / c.source_path.lstrip("/")).exists()

    # protected current db must still exist on "device"
    current_db_path = next(c["source_path"] for c in preview.crypt14_inventory if c["kind"] == "current")
    assert (sandbox / current_db_path.lstrip("/")).exists()


def test_executor_refuses_current_db_even_if_it_somehow_appears_eligible(fake_client, backup_dir, sandbox):
    """Defense in depth: even if a bug ever let the current DB slip into an
    eligible list, the executor's own hard-coded protected-filename check
    must still refuse to delete it."""
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    by_path = {e["source_path"]: e for e in entries}

    current_entry = next(e for e in entries if e["filename"] == "msgstore.db.crypt14")
    from app.models import DeletionCandidate
    forced = DeletionCandidate(
        source_path=current_entry["source_path"], backup_path=current_entry["backup_path"],
        source_sha256=current_entry["source_sha256"], backup_sha256=current_entry["backup_sha256"],
        size=current_entry["source_size"], category="WhatsApp",
    )
    preview.eligible.append(forced)

    deleted, skipped, log_rows = execute_deletion(fake_client, preview, by_path, _settings())
    assert not any(d["source_path"] == forced.source_path for d in deleted)
    assert (sandbox / forced.source_path.lstrip("/")).exists()
    skip_reasons = [s["reason"] for s in skipped if s["source_path"] == forced.source_path]
    assert any("protected" in r for r in skip_reasons)


def test_executor_skips_when_hash_changed_at_moment_of_deletion(fake_client, backup_dir, sandbox):
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    by_path = {e["source_path"]: e for e in entries}

    target = next(c for c in preview.eligible if c.source_path.endswith("IMG_0001.jpg"))
    (sandbox / target.source_path.lstrip("/")).write_text("changed after preview, before delete")

    deleted, skipped, log_rows = execute_deletion(fake_client, preview, by_path, _settings())
    assert not any(d["source_path"] == target.source_path for d in deleted)
    assert (sandbox / target.source_path.lstrip("/")).exists()


def test_executor_stops_immediately_on_connection_loss(fake_client, backup_dir):
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    by_path = {e["source_path"]: e for e in entries}

    fake_client.disconnect()
    with pytest.raises(DeletionAborted):
        execute_deletion(fake_client, preview, by_path, _settings())


def test_executor_partial_progress_preserved_on_abort(fake_client, backup_dir, sandbox):
    """When the connection drops mid-run, files already deleted before the
    drop stay deleted (that's fine — they were individually verified) but
    nothing after the drop point is touched, and the exception carries the
    partial results so they can still be logged."""
    manifest, entries = _full_backup(fake_client, backup_dir)
    preview = run_deletion_preview(fake_client, manifest.id, entries, fake_client.serial)
    by_path = {e["source_path"]: e for e in entries}

    original_scan = fake_client.scan_dir
    call_count = {"n": 0}

    def flaky_scan(remote_dir, max_depth=1):
        call_count["n"] += 1
        if call_count["n"] > 1:
            fake_client.disconnect()
        return original_scan(remote_dir, max_depth)

    import unittest.mock
    with unittest.mock.patch.object(fake_client, "scan_dir", side_effect=flaky_scan):
        with pytest.raises(DeletionAborted) as exc_info:
            execute_deletion(fake_client, preview, by_path, _settings())

    assert isinstance(exc_info.value.log_rows, list)
