"""Downloading a release and running it.

This is the only place in the app that fetches a file and then executes
it, so most of these tests are about refusals rather than about the happy
path: a bad checksum, a missing checksum, a host we do not fetch from, a
job already running, a source checkout with nothing to replace.

The Windows branch is exercised from Linux by supplying the Windows-only
subprocess API, because there is no Windows job in CI -- without that, the
one platform the silent-install flow was written for is the one platform
nothing ever checks.
"""
import hashlib
import subprocess
import types
from pathlib import Path

import pytest

from app.updater import apply as apply_mod
from app.updater import shutdown
from app.updater.apply import UpdateError
from app.updater.net import UnsafeUrlError


@pytest.fixture(autouse=True)
def quiet_shutdown(monkeypatch):
    """Nothing in this file may actually close the process."""
    calls = []
    monkeypatch.setattr(shutdown, "request_quit", lambda delay=2.0: calls.append(delay))
    monkeypatch.setattr(apply_mod.shutdown, "request_quit", lambda delay=2.0: calls.append(delay))
    return calls


def _emit(_event):
    pass


# --------------------------------------------------------------------------
# Checksums
# --------------------------------------------------------------------------


def test_checksums_parse_both_coreutils_separators():
    digest = "a" * 64
    text = f"{digest}  text-mode.deb\n{digest} *binary-mode.exe\n"
    parsed = apply_mod.parse_checksums(text)
    assert parsed == {"text-mode.deb": digest, "binary-mode.exe": digest}


def test_malformed_checksum_lines_are_skipped_not_fatal():
    digest = "b" * 64
    text = f"\n# a comment\nnot-a-digest  thing.deb\n{digest}  good.deb\n"
    assert apply_mod.parse_checksums(text) == {"good.deb": digest}


# --------------------------------------------------------------------------
# prepare(): download + verify
# --------------------------------------------------------------------------


def _release(tmp_path, payload=b"installer bytes", name="android-backup-manager_9.9.9_amd64.deb"):
    return {
        "version": "9.9.9",
        "asset": {
            "name": name,
            "url": f"https://github.com/o/r/releases/download/v9.9.9/{name}",
            "size": len(payload),
        },
        "assets": [
            {"name": name, "url": f"https://github.com/o/r/releases/download/v9.9.9/{name}"},
            {"name": "SHA256SUMS", "url": "https://github.com/o/r/releases/download/v9.9.9/SHA256SUMS"},
        ],
    }


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_mod, "DOWNLOAD_DIR", tmp_path / "updates")
    return tmp_path / "updates"


def _stub_download(monkeypatch, payload: bytes):
    def fake(url, dest, expected_size=None, emit=None):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        return dest

    monkeypatch.setattr(apply_mod, "download", fake)


def _stub_checksums(monkeypatch, sums: dict[str, str]):
    monkeypatch.setattr(apply_mod, "fetch_checksums", lambda release: sums)


def test_a_verified_download_is_kept(downloads, monkeypatch):
    payload = b"installer bytes"
    release = _release(downloads, payload)
    _stub_download(monkeypatch, payload)
    _stub_checksums(monkeypatch, {release["asset"]["name"]: hashlib.sha256(payload).hexdigest()})

    path = apply_mod.prepare(release, _emit)
    assert path.read_bytes() == payload


def test_a_mismatched_download_is_refused_and_deleted(downloads, monkeypatch):
    """The whole point of the exercise: an installer that does not match
    what the release published must not survive to be run."""
    release = _release(downloads, b"installer bytes")
    _stub_download(monkeypatch, b"something else entirely")
    _stub_checksums(
        monkeypatch, {release["asset"]["name"]: hashlib.sha256(b"installer bytes").hexdigest()}
    )

    with pytest.raises(UpdateError, match="does not match the checksum"):
        apply_mod.prepare(release, _emit)

    assert not (downloads / release["asset"]["name"]).exists()


def test_a_release_without_a_checksums_asset_is_refused(downloads, monkeypatch):
    release = _release(downloads)
    release["assets"] = [a for a in release["assets"] if a["name"] != "SHA256SUMS"]
    _stub_download(monkeypatch, b"x")

    with pytest.raises(UpdateError, match="publishes no SHA256SUMS"):
        apply_mod.prepare(release, _emit)


def test_an_asset_missing_from_the_checksums_file_is_refused(downloads, monkeypatch):
    release = _release(downloads)
    _stub_download(monkeypatch, b"x")
    _stub_checksums(monkeypatch, {"some-other-file.deb": "c" * 64})

    with pytest.raises(UpdateError, match="not listed in SHA256SUMS"):
        apply_mod.prepare(release, _emit)


def test_a_release_with_no_asset_for_this_platform_is_refused(downloads):
    release = _release(downloads)
    release["asset"] = None
    with pytest.raises(UpdateError, match="no installer built for your platform"):
        apply_mod.prepare(release, _emit)


# --------------------------------------------------------------------------
# download(): where bytes may come from
# --------------------------------------------------------------------------


def test_the_asset_cdn_host_may_move_within_githubusercontent():
    """Regression. github.com redirects an asset download to a CDN host,
    and that host changed from objects.githubusercontent.com to
    release-assets.githubusercontent.com. Pinning the exact name meant
    every download failed with "refusing to fetch from host" -- caught by
    downloading a real release, not by any unit test.
    """
    from app.updater.net import host_allowed

    hosts = apply_mod.DOWNLOAD_HOSTS
    assert host_allowed("github.com", hosts)
    assert host_allowed("objects.githubusercontent.com", hosts)
    assert host_allowed("release-assets.githubusercontent.com", hosts)

    # The wildcard still has to match on a label boundary.
    assert not host_allowed("evilgithubusercontent.com", hosts)
    assert not host_allowed("githubusercontent.com.evil.example", hosts)
    assert not host_allowed("github.com.evil.example", hosts)
    assert not host_allowed("githubusercontent.com", hosts)  # bare, no label
    assert not host_allowed(None, hosts)


def test_downloads_are_refused_from_anywhere_but_github(tmp_path):
    for url in (
        "http://github.com/o/r/x.deb",                 # not HTTPS
        "https://example.com/x.deb",                   # wrong host
        "https://github.com.evil.example/x.deb",       # suffix near-miss
    ):
        with pytest.raises(UnsafeUrlError):
            apply_mod.download(url, tmp_path / "x.deb")


def test_a_truncated_download_is_refused(tmp_path, monkeypatch):
    """Content-Length lying, a dropped connection, a proxy error page --
    all land here, and none of them should leave a file behind."""
    class FakeResponse:
        headers = {"Content-Length": "999"}

        def __init__(self):
            self._chunks = [b"short"]

        def read(self, _n):
            return self._chunks.pop(0) if self._chunks else b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        apply_mod, "opener", lambda hosts: types.SimpleNamespace(open=lambda *a, **k: FakeResponse())
    )

    dest = tmp_path / "x.deb"
    with pytest.raises(UpdateError, match="download was 5 bytes"):
        apply_mod.download("https://github.com/o/r/x.deb", dest, expected_size=999)

    assert not dest.exists()
    assert not dest.with_suffix(".deb.part").exists()


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------


@pytest.fixture
def fake_win32(monkeypatch):
    monkeypatch.setattr(apply_mod.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "DETACHED_PROCESS", 0x00000008, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False)


def test_windows_runs_the_installer_silently_and_then_closes(
    tmp_path, monkeypatch, fake_win32, quiet_shutdown
):
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return types.SimpleNamespace(pid=1234)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    installer = tmp_path / "Setup.exe"
    installer.write_bytes(b"x")

    result = apply_mod.apply_windows(installer, "9.9.9", _emit)

    assert seen["cmd"][0] == str(installer)
    # /SILENT rather than /VERYSILENT: a progress window is reassuring
    # when the app has just closed itself.
    assert "/SILENT" in seen["cmd"]
    assert "/CLOSEAPPLICATIONS" in seen["cmd"]
    assert "/RESTARTAPPLICATIONS" in seen["cmd"]
    # Detached, or the installer dies with the process that is about to exit.
    assert seen["kwargs"]["creationflags"] & subprocess.DETACHED_PROCESS

    assert result["action"] == "closing"
    # The app must close, or the installer cannot replace files it holds
    # open -- but not instantly, or the user never sees what happened.
    assert quiet_shutdown and quiet_shutdown[0] >= 1.0


# --------------------------------------------------------------------------
# Linux
# --------------------------------------------------------------------------


def _fake_pkexec(monkeypatch, returncode, stderr=""):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return types.SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(apply_mod.shutil, "which", lambda name: "/usr/bin/pkexec")
    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


def test_linux_installs_through_pkexec_and_asks_for_a_restart(tmp_path, monkeypatch):
    seen = _fake_pkexec(monkeypatch, 0)
    package = tmp_path / "app_9.9.9_amd64.deb"
    package.write_bytes(b"x")

    result = apply_mod.apply_linux(package, "9.9.9", _emit)

    # apt-get, not `dpkg -i`: an upgrade that adds a dependency has to
    # resolve it rather than leave dpkg half-configured.
    assert seen["cmd"][:2] == ["/usr/bin/pkexec", "apt-get"]
    assert str(package) in seen["cmd"]
    # Linux can replace a running program's files, so the app is still
    # alive here and the restart is the user's to trigger.
    assert result["action"] == "restart_required"


def test_dismissing_the_password_prompt_changes_nothing(tmp_path, monkeypatch):
    _fake_pkexec(monkeypatch, 126)
    package = tmp_path / "x.deb"
    package.write_bytes(b"x")

    with pytest.raises(UpdateError, match="dismissed"):
        apply_mod.apply_linux(package, "9.9.9", _emit)


def test_a_failing_package_manager_is_reported_not_swallowed(tmp_path, monkeypatch):
    _fake_pkexec(monkeypatch, 100, stderr="E: Unable to correct problems")
    package = tmp_path / "x.deb"
    package.write_bytes(b"x")

    with pytest.raises(UpdateError, match="Unable to correct problems"):
        apply_mod.apply_linux(package, "9.9.9", _emit)


def test_without_pkexec_the_verified_package_is_handed_over_with_a_command(
    tmp_path, monkeypatch
):
    """No pkexec means no way to become root from here. The download was
    still verified, so say where it is rather than throwing it away."""
    monkeypatch.setattr(apply_mod.shutil, "which", lambda name: None)
    package = tmp_path / "x.deb"
    package.write_bytes(b"x")

    result = apply_mod.apply_linux(package, "9.9.9", _emit)
    assert result["action"] == "manual"
    assert str(package) in result["command"]
    assert result["path"] == str(package)


# --------------------------------------------------------------------------
# run_update() / restart() guards
# --------------------------------------------------------------------------


def test_a_source_checkout_is_never_installed_over(monkeypatch):
    monkeypatch.setattr(apply_mod, "is_release_build", lambda: False)

    with pytest.raises(UpdateError, match="source checkout"):
        apply_mod.run_update(_emit)
    with pytest.raises(UpdateError, match="installed copy"):
        apply_mod.restart()


def test_nothing_is_installed_when_there_is_no_newer_release(monkeypatch):
    monkeypatch.setattr(apply_mod, "is_release_build", lambda: True)
    monkeypatch.setattr(apply_mod, "check", lambda: {"available": False, "latest": None})

    with pytest.raises(UpdateError, match="no newer release"):
        apply_mod.run_update(_emit)
