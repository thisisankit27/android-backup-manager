"""The update check is the only outbound request this app ever makes.

Two things are being pinned here. First, that it stays silent until the
user has agreed to it -- the product's entire claim is that nothing leaves
the machine, so "we asked first" has to be enforced, not just intended.
Second, that every ordinary failure (offline, rate-limited, no releases
yet) comes back as "no update" rather than as an error in the user's face.
"""
import json
import time

import pytest

from app.updater import check as check_mod
from app.updater import versions
from app.updater.net import UnsafeUrlError, assert_allowed

# --------------------------------------------------------------------------
# Version ordering
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate,current",
    [
        ("0.1.3", "0.1.2"),
        ("0.2.0", "0.1.99"),
        ("1.0.0", "0.9.9"),
        ("0.1.2", "0.1.2-rc1"),      # a release beats its own candidate
        ("0.1.2-rc2", "0.1.2-rc1"),
        ("0.1.2-rc10", "0.1.2-rc9"),  # not a string comparison
        ("v0.1.3", "0.1.2"),          # tag form
        ("0.1.2", "0.0.0-dev"),
    ],
)
def test_newer_versions_are_recognised(candidate, current):
    assert versions.is_newer(candidate, current)


@pytest.mark.parametrize(
    "candidate,current",
    [
        ("0.1.2", "0.1.2"),
        ("0.1.2", "0.1.3"),
        ("0.1.2-rc1", "0.1.2"),
        ("0.1.2", "1.0.0"),
    ],
)
def test_older_or_equal_versions_are_not_offered(candidate, current):
    assert not versions.is_newer(candidate, current)


def test_unparseable_versions_do_not_raise():
    """A malformed tag on the release feed must not break the running app."""
    assert versions.parse("") == ((0, 0, 0), "")
    assert versions.parse("garbage") == ((0, 0, 0), "")
    assert not versions.is_newer("garbage", "0.1.2")


# --------------------------------------------------------------------------
# Where we are allowed to fetch from
# --------------------------------------------------------------------------


def test_only_https_github_is_fetchable():
    assert_allowed("https://api.github.com/repos/x/y/releases/latest", ("api.github.com",))

    with pytest.raises(UnsafeUrlError):
        assert_allowed("http://api.github.com/x", ("api.github.com",))
    with pytest.raises(UnsafeUrlError):
        assert_allowed("https://evil.example.com/x", ("api.github.com",))
    # The classic near-miss: a host that merely ends with the allowed one.
    with pytest.raises(UnsafeUrlError):
        assert_allowed("https://api.github.com.evil.example/x", ("api.github.com",))


# --------------------------------------------------------------------------
# Asset selection
# --------------------------------------------------------------------------


def test_windows_picks_the_installer_and_linux_the_matching_deb(monkeypatch):
    assets = [
        {"name": "AndroidBackupManager-0.2.0-Setup.exe"},
        {"name": "android-backup-manager_0.2.0_amd64.deb"},
        {"name": "SHA256SUMS"},
    ]

    monkeypatch.setattr(check_mod.sys, "platform", "win32")
    assert check_mod.pick_asset(assets)["name"].endswith(".exe")

    monkeypatch.setattr(check_mod.sys, "platform", "linux")
    monkeypatch.setattr(check_mod.platform, "machine", lambda: "x86_64")
    assert check_mod.pick_asset(assets)["name"].endswith("_amd64.deb")


def test_platforms_with_no_build_are_reported_rather_than_mismatched(monkeypatch):
    """Handing an arm64 Linux user the amd64 .deb would be worse than
    telling them there is no build for their machine."""
    monkeypatch.setattr(check_mod.sys, "platform", "linux")
    monkeypatch.setattr(check_mod.platform, "machine", lambda: "riscv64")
    assert check_mod.asset_suffix() is None
    assert check_mod.pick_asset([{"name": "x_amd64.deb"}]) is None

    monkeypatch.setattr(check_mod.sys, "platform", "darwin")
    assert check_mod.asset_suffix() is None


# --------------------------------------------------------------------------
# check()
# --------------------------------------------------------------------------


@pytest.fixture
def update_sandbox(tmp_path, monkeypatch):
    """Point the settings file and the check cache at a temp directory."""
    from app import config

    monkeypatch.setattr(config, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(check_mod, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(check_mod, "CACHE_PATH", tmp_path / "update-check.json")
    monkeypatch.setattr(check_mod, "VERSION", "0.1.2")
    monkeypatch.setattr(check_mod, "is_release_build", lambda: True)
    monkeypatch.setattr(check_mod.sys, "platform", "linux")
    monkeypatch.setattr(check_mod.platform, "machine", lambda: "x86_64")
    return tmp_path


def _release_payload(version="0.2.0"):
    return json.dumps(
        {
            "tag_name": f"v{version}",
            "body": "notes",
            "published_at": "2026-08-01T00:00:00Z",
            "html_url": "https://github.com/x/y/releases/tag/v" + version,
            "assets": [
                {
                    "name": f"android-backup-manager_{version}_amd64.deb",
                    "browser_download_url": "https://github.com/x/y/releases/download/a.deb",
                    "size": 38_000_000,
                },
                {
                    "name": "SHA256SUMS",
                    "browser_download_url": "https://github.com/x/y/releases/download/SHA256SUMS",
                    "size": 200,
                },
            ],
        }
    ).encode()


def _set_enabled(value):
    from app.config import Settings, save_settings

    save_settings(Settings(update_check_enabled=value))


def test_nothing_is_fetched_before_the_user_has_been_asked(update_sandbox, monkeypatch):
    """The whole point of the tri-state. Until the answer is yes, the
    network is not touched at all."""
    def explode(*a, **k):
        raise AssertionError("a request was made without consent")

    monkeypatch.setattr(check_mod, "fetch", explode)

    result = check_mod.check()
    assert result["asked"] is False
    assert result["enabled"] is False
    assert result["available"] is False
    assert result["latest"] is None


def test_nothing_is_fetched_after_the_user_declines(update_sandbox, monkeypatch):
    _set_enabled(False)
    monkeypatch.setattr(
        check_mod, "fetch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched"))
    )

    result = check_mod.check()
    assert result["asked"] is True
    assert result["enabled"] is False


def test_a_newer_release_is_offered_once_enabled(update_sandbox, monkeypatch):
    _set_enabled(True)
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("0.2.0"))

    result = check_mod.check()
    assert result["available"] is True
    assert result["latest"]["version"] == "0.2.0"
    assert result["latest"]["asset"]["name"].endswith("_amd64.deb")
    assert result["error"] is None


def test_the_same_version_is_not_offered_to_itself(update_sandbox, monkeypatch):
    _set_enabled(True)
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("0.1.2"))
    assert check_mod.check()["available"] is False


def test_being_offline_is_not_an_error_the_user_sees(update_sandbox, monkeypatch):
    _set_enabled(True)

    def offline(*a, **k):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(check_mod, "fetch", offline)

    result = check_mod.check()
    assert result["available"] is False
    assert result["latest"] is None
    assert "unreachable" in result["error"]


def test_the_check_runs_at_most_once_a_day(update_sandbox, monkeypatch):
    _set_enabled(True)
    calls = []

    def counted(*a, **k):
        calls.append(1)
        return _release_payload("0.2.0")

    monkeypatch.setattr(check_mod, "fetch", counted)

    check_mod.check()
    check_mod.check()
    check_mod.check()
    assert len(calls) == 1

    # ...unless the user asks explicitly, which is what the Options
    # "Check now" button does.
    check_mod.check(force=True)
    assert len(calls) == 2


def test_a_stale_cache_is_refetched(update_sandbox, monkeypatch):
    _set_enabled(True)
    (update_sandbox / "update-check.json").write_text(
        json.dumps(
            {
                "checked_at": time.time() - check_mod.CHECK_INTERVAL - 1,
                "release": {"version": "0.1.1"},
                "error": None,
            }
        )
    )
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("0.2.0"))
    assert check_mod.check()["latest"]["version"] == "0.2.0"


def test_a_failed_check_retries_sooner_than_a_successful_one(update_sandbox, monkeypatch):
    _set_enabled(True)
    (update_sandbox / "update-check.json").write_text(
        json.dumps({"checked_at": time.time() - 2 * 60 * 60, "release": None, "error": "offline"})
    )
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("0.2.0"))

    # Two hours is fresh for a success and stale for a failure.
    assert check_mod.check()["latest"]["version"] == "0.2.0"


def test_a_source_checkout_is_never_offered_an_update(update_sandbox, monkeypatch):
    """0.0.0-dev has no installed copy for an installer to replace."""
    _set_enabled(True)
    monkeypatch.setattr(check_mod, "VERSION", "0.0.0-dev")
    monkeypatch.setattr(check_mod, "is_release_build", lambda: False)
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("9.9.9"))

    result = check_mod.check()
    assert result["available"] is False
    assert result["latest"]["version"] == "9.9.9"  # still reported, just not offered


def test_a_dismissed_version_is_marked_as_such(update_sandbox, monkeypatch):
    from app.config import Settings, save_settings

    save_settings(Settings(update_check_enabled=True, update_dismissed_version="0.2.0"))
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("0.2.0"))

    result = check_mod.check()
    assert result["available"] is True
    assert result["dismissed"] is True

    # A newer release than the dismissed one is announced again.
    (update_sandbox / "update-check.json").unlink()
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: _release_payload("0.3.0"))
    assert check_mod.check()["dismissed"] is False


def test_a_release_with_no_asset_for_this_platform_is_not_offered_a_download(
    update_sandbox, monkeypatch
):
    payload = json.loads(_release_payload("0.2.0"))
    payload["assets"] = [{"name": "AndroidBackupManager-0.2.0-Setup.exe"}]
    monkeypatch.setattr(check_mod, "fetch", lambda *a, **k: json.dumps(payload).encode())
    _set_enabled(True)

    result = check_mod.check()
    assert result["available"] is True
    assert result["latest"]["asset"] is None
