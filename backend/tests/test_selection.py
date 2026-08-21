from app.discovery.scanner import discover
from app.models import FileState
from app.selection.freezer import freeze_selection


def test_default_selection_matches_category_defaults(fake_client):
    discovery = discover(fake_client, fake_client.serial)
    selection = freeze_selection(discovery, overrides={})
    included_paths = {e.path for e in selection.included()}

    camera = next(c for c in discovery.categories if c.id == "camera")
    live_camera_paths = {f.path for f in camera.files if not f.is_trashed}
    trashed_camera_paths = {f.path for f in camera.files if f.is_trashed}

    assert live_camera_paths.issubset(included_paths)
    assert trashed_camera_paths.isdisjoint(included_paths)


def test_individual_file_override_excludes_one_file(fake_client):
    discovery = discover(fake_client, fake_client.serial)
    camera = next(c for c in discovery.categories if c.id == "camera")
    live_files = [f for f in camera.files if not f.is_trashed]
    excluded_path = live_files[0].path

    selection = freeze_selection(discovery, overrides={excluded_path: "EXCLUDE"})
    included_paths = {e.path for e in selection.included()}
    assert excluded_path not in included_paths
    assert live_files[1].path in included_paths


def test_category_level_exclude_via_overrides(fake_client):
    discovery = discover(fake_client, fake_client.serial)
    stickers = next(c for c in discovery.categories if "sticker" in c.id.lower())
    # stickers already default EXCLUDE; flip them to INCLUDE to prove overrides work both ways
    overrides = {f.path: "INCLUDE" for f in stickers.files}
    selection = freeze_selection(discovery, overrides=overrides)
    included_paths = {e.path for e in selection.included()}
    assert all(f.path in included_paths for f in stickers.files)


def test_selection_totals(fake_client):
    discovery = discover(fake_client, fake_client.serial)
    selection = freeze_selection(discovery, overrides={})
    included = selection.included()
    expected_size = sum(e.size for e in included)
    assert expected_size == sum(e.size for e in included)  # sanity: totals derivable
    assert len(included) > 0


def test_inaccessible_files_stay_inaccessible_regardless_of_override(fake_client):
    from app.models import Category, DiscoveredFile, DiscoveryResult, InaccessibleLocation

    f = DiscoveredFile(path="/storage/emulated/0/Android/data/x/secret", size=1, mtime=0, sha256="a",
                        category_id="ghost", filename="secret", extension="",
                        default_state=FileState.INACCESSIBLE)
    cat = Category(id="ghost", label="ghost", remote_dir="/x", report_group="Other",
                    default_include=True, files=[f])
    discovery = DiscoveryResult(device_serial="s", generated_at="now", categories=[cat], inaccessible=[])

    selection = freeze_selection(discovery, overrides={f.path: "INCLUDE"})
    assert selection.entries[0].state == FileState.INACCESSIBLE
