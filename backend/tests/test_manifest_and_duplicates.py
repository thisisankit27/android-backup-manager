import json

from app.audit.store import write_backup_manifest
from app.backup.engine import run_backup
from app.discovery.scanner import discover
from app.manifest.duplicates import find_duplicate_groups
from app.models import BackupManifest
from app.selection.freezer import freeze_selection


def _backup_everything(fake_client, backup_dir, backup_id="b1"):
    discovery = discover(fake_client, fake_client.serial)
    overrides = {f.path: "INCLUDE" for cat in discovery.categories for f in cat.files}
    selection = freeze_selection(discovery, overrides=overrides)
    return run_backup(fake_client, selection, backup_dir, backup_id=backup_id)


def test_manifest_json_and_csv_written(fake_client, backup_dir):
    manifest = _backup_everything(fake_client, backup_dir)
    manifest.backup_dir = str(backup_dir)
    json_path = write_backup_manifest(manifest)

    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert len(data) == len(manifest.entries)

    csv_path = backup_dir / "_audit" / "manifest.csv"
    assert csv_path.exists()
    assert "source_sha256" in csv_path.read_text().splitlines()[0]


def test_manifest_sha256_recorded(fake_client, backup_dir):
    manifest = _backup_everything(fake_client, backup_dir)
    manifest.backup_dir = str(backup_dir)
    write_backup_manifest(manifest)
    sha_file = backup_dir / "_audit" / "manifest.sha256"
    assert sha_file.exists()
    assert len(sha_file.read_text().split()[0]) == 64  # sha256 hex digest length


def test_duplicate_content_detected_across_different_paths(fake_client, backup_dir):
    """Documents/document_copy.pdf and Download/document.pdf share identical
    fixture content — both must survive in the manifest (no silent dedup),
    and be reported as one duplicate group."""
    manifest = _backup_everything(fake_client, backup_dir)
    manifest.backup_dir = str(backup_dir)
    write_backup_manifest(manifest)

    entries = json.loads((backup_dir / "_audit" / "manifest.json").read_text())
    paths_present = {e["source_path"] for e in entries}
    assert any(p.endswith("document.pdf") for p in paths_present)
    assert any(p.endswith("document_copy.pdf") for p in paths_present)

    groups = find_duplicate_groups(entries)
    matching = [g for g in groups if any(p.endswith("document.pdf") for p in g["paths"])]
    assert len(matching) == 1
    assert matching[0]["count"] == 2
