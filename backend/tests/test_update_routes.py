"""The update endpoints, and the one refusal that matters most.

An update must never land in the middle of a backup or a deletion. This
app copies photos off a phone and then deletes them; swapping the binary
underneath a half-finished run is the kind of thing that loses files.
"""
import threading

import pytest
from fastapi.testclient import TestClient

from app.api.jobs import jobs
from app.main import app


@pytest.fixture(autouse=True)
def never_actually_exit_or_spawn(monkeypatch):
    """Hard guard for this file.

    /api/update/restart's job is to launch a new process and then kill
    this one. Under pytest "this one" is the test runner, and the failure
    mode is the suite vanishing mid-run with a green-looking report. The
    restart test below also pins is_release_build explicitly rather than
    relying on the checkout being a dev build -- which is exactly what
    stopped being true the moment a release version was stamped in
    locally.
    """
    import subprocess

    from app.updater import apply as apply_mod

    monkeypatch.setattr(apply_mod.shutdown, "request_quit", lambda delay=2.0: None)
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: pytest.fail("a process was spawned")
    )


@pytest.fixture
def client():
    return TestClient(app)


def test_installing_is_refused_while_another_job_is_running(client, monkeypatch):
    release = threading.Event()

    def slow(emit):
        release.wait(timeout=5)
        return {}

    job_id = jobs.start("backup", slow)
    try:
        response = client.post("/api/update/install")
        assert response.status_code == 409
        assert "backup" in response.json()["detail"]
    finally:
        release.set()
        assert job_id


def test_installing_is_allowed_once_nothing_is_running(client, monkeypatch):
    from app.api import routes_update

    started = {}

    def fake_start(kind, task):
        started["kind"] = kind
        return "job123"

    monkeypatch.setattr(routes_update.jobs, "start", fake_start)
    monkeypatch.setattr(routes_update.jobs, "active_kinds", lambda exclude=(): [])

    response = client.post("/api/update/install")
    assert response.status_code == 200
    assert response.json() == {"job_id": "job123"}
    assert started["kind"] == "update_install"


def test_the_check_endpoint_answers_even_with_no_network(client, monkeypatch):
    """A failed check must not paint an error over the app."""
    from app.updater import check as check_mod

    monkeypatch.setattr(check_mod, "load_settings", lambda: _enabled_settings())
    monkeypatch.setattr(check_mod, "_read_cache", lambda: None)
    monkeypatch.setattr(check_mod, "_write_cache", lambda entry: None)

    def offline(*a, **k):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(check_mod, "fetch", offline)

    response = client.get("/api/update/check")
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_restarting_is_refused_from_a_source_checkout(client, monkeypatch):
    from app.updater import apply as apply_mod

    monkeypatch.setattr(apply_mod, "is_release_build", lambda: False)

    response = client.post("/api/update/restart")
    assert response.status_code == 409
    assert "installed copy" in response.json()["detail"]


def test_the_preference_endpoint_records_the_answer(client, monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")

    from app.updater import check as check_mod

    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: (_ for _ in ()).throw(OSError("no net")))
    monkeypatch.setattr(check_mod, "CACHE_PATH", tmp_path / "update-check.json")
    monkeypatch.setattr(check_mod, "APP_DATA_DIR", tmp_path)

    assert client.post("/api/update/preference", json={"enabled": False}).json()["asked"] is True
    assert config.load_settings().update_check_enabled is False

    assert client.post("/api/update/preference", json={"enabled": True}).json()["enabled"] is True
    assert config.load_settings().update_check_enabled is True


def _enabled_settings():
    from app.config import Settings

    return Settings(update_check_enabled=True)
