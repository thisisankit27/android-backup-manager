from app.backup.engine import run_backup
from app.discovery.scanner import discover
from app.selection.freezer import freeze_selection


def _select_everything(fake_client):
    discovery = discover(fake_client, fake_client.serial)
    overrides = {}
    for cat in discovery.categories:
        for f in cat.files:
            overrides[f.path] = "INCLUDE"
    return freeze_selection(discovery, overrides=overrides)


def test_successful_copy_and_verification(fake_client, backup_dir):
    selection = _select_everything(fake_client)
    manifest = run_backup(fake_client, selection, backup_dir, backup_id="b1")

    assert len(manifest.entries) == len(selection.included())
    assert all(e.verification_status == "verified" for e in manifest.entries)
    for e in manifest.entries:
        assert e.source_sha256 == e.backup_sha256
        assert e.source_size == e.backup_size


def test_excluded_files_never_copied(fake_client, backup_dir):
    discovery = discover(fake_client, fake_client.serial)
    # only include camera live files; explicitly leave everything else at its default
    selection = freeze_selection(discovery, overrides={})
    manifest = run_backup(fake_client, selection, backup_dir, backup_id="b2")

    backed_up_paths = {e.source_path for e in manifest.entries}
    stickers_cat = next(c for c in discovery.categories if "sticker" in c.id.lower())
    for f in stickers_cat.files:
        assert f.path not in backed_up_paths

    camera_cat = next(c for c in discovery.categories if c.id == "camera")
    for f in camera_cat.files:
        if f.is_trashed:
            assert f.path not in backed_up_paths


def test_failed_copy_when_source_disappears_before_backup(fake_client, backup_dir, sandbox):
    selection = _select_everything(fake_client)
    # simulate the file vanishing between selection freeze and backup start
    (sandbox / "storage/emulated/0/DCIM/Camera/IMG_0001.jpg").unlink()

    manifest = run_backup(fake_client, selection, backup_dir, backup_id="b3")
    entry = next(e for e in manifest.entries if e.source_path.endswith("IMG_0001.jpg"))
    assert entry.verification_status == "failed"
    assert entry.copy_status == "failed"


def test_corrupted_transfer_is_marked_verification_failed_not_verified(fake_client, backup_dir, monkeypatch):
    """A file whose locally-pulled bytes don't match the freshly-scanned
    remote hash must never be marked verified, even though the copy
    'succeeded' in the sense that a local file exists."""
    selection = _select_everything(fake_client)

    original_pull_dir = fake_client.pull_dir
    original_pull = fake_client.pull

    def corrupt_if_target(local_path):
        if local_path.name == "IMG_0002.jpg":
            local_path.write_bytes(b"corrupted-during-transfer")

    def corrupting_pull_dir(remote_dir, local_dir):
        original_pull_dir(remote_dir, local_dir)
        corrupt_if_target(local_dir / "IMG_0002.jpg")

    def corrupting_pull(remote_path, local_path):
        original_pull(remote_path, local_path)
        corrupt_if_target(local_path)

    monkeypatch.setattr(fake_client, "pull_dir", corrupting_pull_dir)
    monkeypatch.setattr(fake_client, "pull", corrupting_pull)

    manifest = run_backup(fake_client, selection, backup_dir, backup_id="b4")
    entry = next(e for e in manifest.entries if e.source_path.endswith("IMG_0002.jpg"))
    assert entry.verification_status == "verification_failed"
    assert entry.source_sha256 != entry.backup_sha256
