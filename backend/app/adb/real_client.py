"""Real adb-backed implementation of AdbClient.

Every subprocess invocation uses a list of arguments (never shell=True), so
there is no local shell interpolation. The one place a string is built is
the *remote* command passed to `adb shell` — adb shell always takes a single
command string to run on the device's own shell, so any path embedded in it
is shlex.quote()'d before being placed there.
"""
import shlex
import subprocess
from pathlib import Path

from app.adb.client import AdbClient
from app.adb.errors import AdbError, AmbiguousDeviceError, NoDeviceError
from app.adb.types import DeletionAttemptResult, DeletionOutcome, DeviceInfo, RemoteEntry


def _run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _check(result: subprocess.CompletedProcess, context: str) -> None:
    if result.returncode != 0:
        raise AdbError(f"{context} failed (exit {result.returncode}): {result.stderr.strip()}")
    stderr_lower = result.stderr.lower()
    if "error:" in stderr_lower or "device offline" in stderr_lower or "no devices" in stderr_lower:
        raise AdbError(f"{context} reported an adb error: {result.stderr.strip()}")


class RealAdbClient(AdbClient):
    def __init__(self, serial: str | None = None):
        self.serial = serial

    def _adb(self, *args: str) -> list[str]:
        base = ["adb"]
        if self.serial:
            base += ["-s", self.serial]
        return base + list(args)

    def list_authorized_devices(self) -> list[str]:
        result = _run(["adb", "devices", "-l"])
        _check(result, "adb devices")
        lines = [l for l in result.stdout.splitlines()[1:] if l.strip()]
        return [l.split()[0] for l in lines if " device " in f" {l} "]

    def get_device_info(self, serial: str) -> DeviceInfo:
        client = RealAdbClient(serial)

        def prop(name: str) -> str:
            r = _run(client._adb("shell", "getprop", name))
            _check(r, f"getprop {name}")
            return r.stdout.strip()

        manufacturer = prop("ro.product.manufacturer")
        model = prop("ro.product.model")
        version = prop("ro.build.version.release")
        sdk_str = prop("ro.build.version.sdk")

        total = used = free = None
        df_result = _run(client._adb("shell", "df", "/storage/emulated/0"))
        if df_result.returncode == 0:
            lines = [l for l in df_result.stdout.splitlines() if l.strip()]
            if len(lines) >= 2:
                parts = lines[-1].split()
                # BusyBox/toolbox df: Filesystem 1K-blocks Used Available Use% Mounted
                if len(parts) >= 4 and parts[1].isdigit():
                    total = int(parts[1]) * 1024
                    used = int(parts[2]) * 1024
                    free = int(parts[3]) * 1024

        return DeviceInfo(
            serial=serial,
            manufacturer=manufacturer,
            model=model,
            android_version=version,
            sdk=int(sdk_str) if sdk_str.isdigit() else 0,
            storage_total_bytes=total,
            storage_used_bytes=used,
            storage_free_bytes=free,
        )

    def scan_dir(self, remote_dir: str, max_depth: int | None = 1) -> dict[str, RemoteEntry]:
        depth_flag = f"-maxdepth {max_depth} " if max_depth is not None else ""
        quoted = shlex.quote(remote_dir)

        hash_cmd = f"find {quoted} {depth_flag}-type f -exec sha256sum {{}} +"
        hash_result = _run(self._adb("shell", hash_cmd))
        _check(hash_result, f"remote hash scan of {remote_dir}")
        hashes: dict[str, str] = {}
        for line in hash_result.stdout.splitlines():
            if not line.strip():
                continue
            h, path = line.split("  ", 1)
            hashes[path] = h.strip()

        meta_cmd = f"find {quoted} {depth_flag}-type f -printf '%T@|%s|%p\\n'"
        meta_result = _run(self._adb("shell", meta_cmd))
        _check(meta_result, f"remote metadata scan of {remote_dir}")

        entries: dict[str, RemoteEntry] = {}
        for line in meta_result.stdout.splitlines():
            if not line.strip() or "|" not in line:
                continue
            mtime_s, size_s, path = line.split("|", 2)
            sha = hashes.get(path)
            if sha is None:
                continue
            try:
                entries[path] = RemoteEntry(path=path, size=int(size_s), mtime=float(mtime_s), sha256=sha)
            except ValueError:
                continue
        return entries

    def path_exists(self, remote_path: str) -> bool:
        quoted = shlex.quote(remote_path)
        result = _run(self._adb("shell", f"[ -e {quoted} ] && echo YES || echo NO"))
        _check(result, f"existence check of {remote_path}")
        return result.stdout.strip() == "YES"

    def list_subdirs(self, remote_dir: str) -> list[str]:
        quoted = shlex.quote(remote_dir)
        result = _run(self._adb("shell", f"[ -d {quoted} ] && find {quoted} -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' || true"))
        _check(result, f"list_subdirs of {remote_dir}")
        return [l for l in result.stdout.splitlines() if l.strip()]

    def pull(self, remote_path: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        result = _run(self._adb("pull", remote_path, str(local_path)))
        _check(result, f"pull of {remote_path}")

    def pull_dir(self, remote_dir: str, local_dir: Path) -> None:
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        result = _run(self._adb("pull", remote_dir, str(local_dir)))
        _check(result, f"pull of directory {remote_dir}")

    def verify_and_delete(self, remote_path: str, expected_sha256: str, dry_run: bool = False) -> DeletionAttemptResult:
        p = shlex.quote(remote_path)
        if dry_run:
            script = (
                f'if [ -e {p} ]; then '
                f'h=$(sha256sum {p} | cut -d" " -f1); '
                f'if [ "$h" = "{expected_sha256}" ]; then echo WOULD_DELETE; '
                f'else echo "HASH_MISMATCH:$h"; fi; '
                f'else echo GONE; fi'
            )
        else:
            script = (
                f'if [ -e {p} ]; then '
                f'h=$(sha256sum {p} | cut -d" " -f1); '
                f'if [ "$h" = "{expected_sha256}" ]; then '
                f'rm -f {p} && ( [ -e {p} ] && echo STILL_EXISTS || echo DELETED ) || echo RM_FAILED; '
                f'else echo "HASH_MISMATCH:$h"; fi; '
                f'else echo GONE; fi'
            )
        result = _run(self._adb("shell", script))
        _check(result, f"delete of {remote_path}")
        outcome = result.stdout.strip()

        if outcome.startswith("HASH_MISMATCH"):
            observed = outcome.split(":", 1)[1] if ":" in outcome else None
            return DeletionAttemptResult(DeletionOutcome.HASH_MISMATCH, observed)
        try:
            return DeletionAttemptResult(DeletionOutcome(outcome))
        except ValueError:
            raise AdbError(f"unexpected remote deletion result for {remote_path}: {outcome!r}")


def check_single_device(expected_serial: str | None = None) -> str:
    """Convenience used by API routes: exactly one authorized device, and,
    if expected_serial is given, it must match (ambiguous-identity guard)."""
    client = RealAdbClient()
    devices = client.list_authorized_devices()
    if not devices:
        raise NoDeviceError("no authorized adb device found")
    if len(devices) > 1:
        raise AmbiguousDeviceError("multiple devices attached; refusing to guess which one")
    serial = devices[0]
    if expected_serial and serial != expected_serial:
        raise AmbiguousDeviceError(
            f"connected device serial {serial} does not match the expected device ({expected_serial})"
        )
    return serial
