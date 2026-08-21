import shutil
from pathlib import Path

import pytest

from app.adb.fake_client import FakeAdbClient

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_device"


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """Never let a test touch the real ~/.android-backup-manager directory."""
    from app.audit import store as store_module
    state_dir = tmp_path / "app_state"
    monkeypatch.setattr(store_module, "STATE_DIR", state_dir)
    monkeypatch.setattr(store_module, "DISCOVERIES_DIR", state_dir / "discoveries")
    monkeypatch.setattr(store_module, "SELECTIONS_DIR", state_dir / "selections")
    monkeypatch.setattr(store_module, "HISTORY_PATH", state_dir / "history.json")
    yield state_dir


@pytest.fixture()
def sandbox(tmp_path) -> Path:
    """A throwaway copy of the sample device fixture, so tests can freely
    mutate/delete files without touching the checked-in fixture."""
    dest = tmp_path / "sample_device"
    shutil.copytree(FIXTURE_ROOT, dest)
    return dest


@pytest.fixture()
def fake_client(sandbox) -> FakeAdbClient:
    return FakeAdbClient(root=sandbox)


@pytest.fixture()
def backup_dir(tmp_path) -> Path:
    d = tmp_path / "Android_Backup_TEST"
    d.mkdir()
    (d / "_audit").mkdir()
    return d
