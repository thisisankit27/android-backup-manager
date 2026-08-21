from app.discovery.scanner import discover
from app.models import FileState


def test_discovers_known_categories(fake_client):
    result = discover(fake_client, fake_client.serial)
    cat_ids = {c.id for c in result.categories}
    assert "camera" in cat_ids
    assert "screenshots" in cat_ids
    assert "download" in cat_ids
    assert any(c.id.startswith("wa_") for c in result.categories)


def test_trashed_files_default_excluded(fake_client):
    result = discover(fake_client, fake_client.serial)
    camera = next(c for c in result.categories if c.id == "camera")
    trashed = [f for f in camera.files if f.is_trashed]
    assert len(trashed) == 1
    assert trashed[0].default_state == FileState.EXCLUDE
    live = [f for f in camera.files if not f.is_trashed]
    assert len(live) == 2
    assert all(f.default_state == FileState.INCLUDE for f in live)


def test_stickers_default_excluded(fake_client):
    result = discover(fake_client, fake_client.serial)
    stickers = next(c for c in result.categories if "sticker" in c.id.lower())
    assert stickers.default_include is False
    assert all(f.default_state == FileState.EXCLUDE for f in stickers.files)


def test_whatsapp_databases_classified(fake_client):
    result = discover(fake_client, fake_client.serial)
    db_cat = next(c for c in result.categories if c.id == "wa_databases")
    kinds = {f.filename: f.crypt14_kind.value for f in db_cat.files}
    assert kinds["msgstore.db.crypt14"] == "current"
    assert kinds["msgstore-2024-01-01.1.db.crypt14"] == "historical"


def test_android_data_reported_inaccessible_not_scanned(fake_client):
    result = discover(fake_client, fake_client.serial)
    assert len(result.inaccessible) == 1
    assert result.inaccessible[0].path.endswith("Android/data")
    # and crucially: no category was built from Android/data contents
    assert not any("com.some.app" in c.remote_dir for c in result.categories)


def test_inaccessible_files_never_marked_include(fake_client):
    # Even if something in Android/data were ever surfaced, it must never
    # default to INCLUDE — inaccessible content must not be silently implied backed up.
    from app.models import DiscoveredFile, FileState
    f = DiscoveredFile(path="/x", size=1, mtime=0, sha256="a", category_id="x",
                        filename="x", extension="", default_state=FileState.INACCESSIBLE)
    assert f.default_state != FileState.INCLUDE
