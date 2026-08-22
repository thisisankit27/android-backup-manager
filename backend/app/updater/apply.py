"""Downloading a release and installing it over the running copy.

This is the only code in the app that fetches a file and then runs it, so
the rules are stricter here than anywhere else:

* HTTPS only, from github.com / objects.githubusercontent.com, with the
  host re-checked on every redirect.
* The download must match the SHA-256 published in the release's
  SHA256SUMS asset. No checksum, no install.
* Nothing starts while any other job is running. This app deletes photos;
  an update must never land in the middle of a backup or a deletion.
* Nothing is ever automatic. Every update is a button someone pressed.

Worth being straight about what the checksum does and does not buy. It
comes from the same release as the installer, so it catches a truncated or
corrupted download, not a compromised release. Only code signing fixes
that, and nothing here is signed yet. It is still much better than running
whatever arrived.
"""
import hashlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import APP_DATA_DIR
from app.updater import shutdown
from app.updater.check import check
from app.updater.net import USER_AGENT, assert_allowed, opener
from app.version import is_release_build

#: github.com issues the download; the bytes come from whichever CDN host
#: it redirects to. That host has changed at least once already --
#: objects.githubusercontent.com became release-assets.githubusercontent.com
#: -- and pinning the exact name meant every download failed. The wildcard
#: matches on label boundaries (see net.host_allowed), and it is not what
#: makes running the file safe: the published SHA-256 is.
DOWNLOAD_HOSTS = ("github.com", "*.githubusercontent.com")
CHECKSUMS_ASSET = "SHA256SUMS"
DOWNLOAD_DIR = APP_DATA_DIR / "updates"

_CHUNK = 256 * 1024
#: Emit progress at most this often, in bytes. A 38 MB .deb would
#: otherwise produce a hundred and fifty events for no benefit.
_PROGRESS_EVERY = 1024 * 1024

#: pkexec's own exit codes, distinct from anything apt-get returns.
_PKEXEC_DISMISSED = 126
_PKEXEC_AUTH_FAILED = 127

#: Long enough for a slow dpkg run plus however long the user takes to
#: find their password, short enough that a wedged prompt does not hang
#: the job forever.
_INSTALL_TIMEOUT = 15 * 60


class UpdateError(Exception):
    """Something is wrong with the update itself — reported to the user."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_checksums(text: str) -> dict[str, str]:
    """Parse a `sha256sum` output file into {filename: digest}.

    Accepts both the two-space (text) and ` *` (binary) separators that
    coreutils emits, and ignores anything malformed rather than raising —
    the entry we need either turns up or it does not.
    """
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts
        if len(digest) != 64:
            continue
        sums[name.lstrip("*").strip()] = digest.lower()
    return sums


def download(url: str, dest: Path, expected_size: int | None = None, emit=None) -> Path:
    """Stream a release asset to disk, reporting progress as it goes."""
    assert_allowed(url, DOWNLOAD_HOSTS)
    dest.parent.mkdir(parents=True, exist_ok=True)

    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    downloaded = 0
    last_emit = 0

    # Written to a .part and renamed only on success, so an interrupted
    # download can never be mistaken for a complete one on the next run.
    partial = dest.with_suffix(dest.suffix + ".part")
    with opener(DOWNLOAD_HOSTS).open(request, timeout=60) as response:
        total = expected_size or int(response.headers.get("Content-Length") or 0) or None
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if emit and downloaded - last_emit >= _PROGRESS_EVERY:
                    last_emit = downloaded
                    emit({"phase": "downloading", "downloaded": downloaded, "total": total})

    if expected_size and downloaded != expected_size:
        partial.unlink(missing_ok=True)
        raise UpdateError(
            f"download was {downloaded} bytes, the release says {expected_size}."
        )

    partial.replace(dest)
    if emit:
        emit({"phase": "downloaded", "downloaded": downloaded, "total": downloaded})
    return dest


def fetch_checksums(release: dict) -> dict[str, str]:
    """The release's SHA256SUMS, or a refusal."""
    asset = next(
        (a for a in release.get("assets") or [] if a.get("name") == CHECKSUMS_ASSET), None
    )
    if asset is None or not asset.get("url"):
        raise UpdateError(
            f"Release {release.get('version')} publishes no {CHECKSUMS_ASSET}, so the "
            "download cannot be verified. Install this update manually instead."
        )

    from app.updater.net import fetch

    return parse_checksums(fetch(asset["url"], DOWNLOAD_HOSTS, timeout=30).decode("utf-8"))


def prepare(release: dict, emit) -> Path:
    """Download the installer for this platform and verify it."""
    asset = release.get("asset")
    if not asset or not asset.get("url"):
        raise UpdateError("This release has no installer built for your platform.")

    emit({"phase": "checksums"})
    sums = fetch_checksums(release)
    expected = sums.get(asset["name"])
    if not expected:
        raise UpdateError(
            f"{asset['name']} is not listed in {CHECKSUMS_ASSET}, so it cannot be verified."
        )

    if DOWNLOAD_DIR.exists():
        # Only ever one update in flight, and a stale half-download from a
        # previous attempt is not something to keep around.
        shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
    target = DOWNLOAD_DIR / asset["name"]

    emit({"phase": "downloading", "downloaded": 0, "total": asset.get("size")})
    download(asset["url"], target, asset.get("size"), emit)

    emit({"phase": "verifying"})
    actual = sha256_file(target)
    if actual != expected:
        target.unlink(missing_ok=True)
        raise UpdateError(
            "The downloaded installer does not match the checksum published with the "
            f"release (expected {expected[:12]}…, got {actual[:12]}…). It has not been run."
        )

    emit({"phase": "verified", "sha256": actual})
    return target


def apply_windows(installer: Path, version: str, emit) -> dict:
    """Hand off to Inno Setup and get out of its way.

    The running app holds its own files open, so the installer cannot
    replace them while we are alive. We start it detached, then close
    ourselves a moment later; its own [Run] entry starts the new version
    when it finishes.
    """
    emit({"phase": "installing"})
    subprocess.Popen(
        [
            str(installer),
            "/SILENT",          # progress bar, no wizard to click through
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
        ],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    shutdown.request_quit(delay=2.5)
    return {
        "action": "closing",
        "version": version,
        "message": (
            f"Installing {version}. This window will close and reopen on the new version."
        ),
    }


def apply_linux(package: Path, version: str, emit) -> dict:
    """Install the .deb through polkit.

    The app lives in /opt, so this needs root. pkexec gives the desktop's
    own password dialog rather than the app inventing one.

    apt-get, not `dpkg -i`: an upgrade that introduces a new dependency
    has to resolve it, instead of leaving dpkg half-configured on a
    machine whose owner just wanted a newer version.
    """
    pkexec = shutil.which("pkexec")
    if not pkexec:
        return {
            "action": "manual",
            "version": version,
            "path": str(package),
            "command": f"sudo apt install {shlex.quote(str(package))}",
            "message": (
                "pkexec is not installed, so the update cannot be applied from here. "
                "The verified package has been downloaded — install it with the "
                "command below."
            ),
        }

    emit({"phase": "installing"})
    try:
        result = subprocess.run(
            [pkexec, "apt-get", "install", "-y", str(package)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=_INSTALL_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        # A password prompt nobody answered, or a dpkg lock held by an
        # apt run in another window. Saying so beats a raw traceback.
        raise UpdateError(
            "The update timed out waiting for the package manager. Nothing was "
            "changed, unless another package operation is still running."
        ) from e

    if result.returncode == _PKEXEC_DISMISSED:
        raise UpdateError("The password prompt was dismissed, so nothing was changed.")
    if result.returncode == _PKEXEC_AUTH_FAILED:
        raise UpdateError("Authentication failed, so nothing was changed.")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise UpdateError(
            "The package manager refused the update"
            + (f": {detail[-1]}" if detail else f" (exit {result.returncode}).")
        )

    # Linux can replace the files of a running program, so unlike Windows
    # we are still here and still working -- on the old code. The restart
    # is the user's to trigger.
    return {
        "action": "restart_required",
        "version": version,
        "message": f"Updated to {version}. Restart the app to start using it.",
    }


def run_update(emit) -> dict:
    """Download, verify and install the latest release."""
    if not is_release_build():
        raise UpdateError(
            "This is a source checkout, not an installed copy — there is nothing "
            "for an installer to replace."
        )

    state = check()
    if not state.get("available") or not state.get("latest"):
        raise UpdateError("There is no newer release to install.")

    release = state["latest"]
    version = release.get("version") or "?"
    installer = prepare(release, emit)

    if sys.platform == "win32":
        return apply_windows(installer, version, emit)
    if sys.platform.startswith("linux"):
        return apply_linux(installer, version, emit)
    raise UpdateError(f"Updating is not supported on {sys.platform}.")


def restart() -> None:
    """Start the newly installed copy and close this one."""
    if not is_release_build():
        raise UpdateError("Restarting into a new version only applies to an installed copy.")

    # Frozen, sys.executable is the app's own binary. apt replaced the
    # file at that path, so exec'ing it picks up the new version; this
    # process keeps running from the inode it already had.
    subprocess.Popen([sys.executable], start_new_session=True, close_fds=True)
    shutdown.request_quit(delay=1.0)
