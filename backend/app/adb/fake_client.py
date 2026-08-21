"""In-process fake AdbClient backed by a plain local directory.

Used by tests so the entire discovery/backup/deletion pipeline — including
the destructive deletion path — can be exercised without ever touching a
real Android device. A test builds a small directory tree (see
tests/fixtures/sample_device) and wraps it in a FakeAdbClient; from the
pipeline's point of view it is indistinguishable from a real phone.

Supports simulating device-loss (`.disconnect()`) and post-scan file
mutation, which is what the deletion-safety tests (changed/missing/hash
mismatch) exercise.
"""
import hashlib
import os
import shutil
from pathlib import Path

from app.adb.client import AdbClient
from app.adb.errors import ConnectionLostError
from app.adb.types import DeletionAttemptResult, DeletionOutcome, DeviceInfo, RemoteEntry


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class FakeAdbClient(AdbClient):
    def __init__(self, root: Path, serial: str = "FAKE_SERIAL_0001", device_info: DeviceInfo | None = None):
        self.root = Path(root)
        self.serial = serial
        self._connected = True
        self._device_info = device_info or DeviceInfo(
            serial=serial, manufacturer="FakeCorp", model="Fake Phone X",
            android_version="15", sdk=35,
            storage_total_bytes=64 * 1024**3, storage_used_bytes=32 * 1024**3, storage_free_bytes=32 * 1024**3,
        )

    def disconnect(self) -> None:
        """Simulate the device going offline mid-operation."""
        self._connected = False

    def reconnect(self) -> None:
        self._connected = True

    def _require_connected(self, context: str) -> None:
        if not self._connected:
            raise ConnectionLostError(f"{context}: device disconnected")

    def _to_local(self, remote_path: str) -> Path:
        # remote paths are always given as /storage/emulated/0/... style; map onto the sandbox root
        rel = remote_path.lstrip("/")
        return self.root / rel

    def list_authorized_devices(self) -> list[str]:
        self._require_connected("list_authorized_devices")
        return [self.serial]

    def get_device_info(self, serial: str) -> DeviceInfo:
        self._require_connected("get_device_info")
        return self._device_info

    def scan_dir(self, remote_dir: str, max_depth: int | None = 1) -> dict[str, RemoteEntry]:
        self._require_connected("scan_dir")
        local_dir = self._to_local(remote_dir)
        entries: dict[str, RemoteEntry] = {}
        if not local_dir.exists():
            return entries
        if max_depth == 1:
            candidates = [p for p in local_dir.iterdir() if p.is_file()]
        else:
            candidates = [p for p in local_dir.rglob("*") if p.is_file()]
        for p in candidates:
            remote_equivalent = "/" + str(p.relative_to(self.root)).replace(os.sep, "/")
            stat = p.stat()
            entries[remote_equivalent] = RemoteEntry(
                path=remote_equivalent, size=stat.st_size, mtime=stat.st_mtime, sha256=_sha256(p)
            )
        return entries

    def path_exists(self, remote_path: str) -> bool:
        self._require_connected("path_exists")
        return self._to_local(remote_path).is_file()

    def list_subdirs(self, remote_dir: str) -> list[str]:
        self._require_connected("list_subdirs")
        local_dir = self._to_local(remote_dir)
        if not local_dir.is_dir():
            return []
        return [p.name for p in local_dir.iterdir() if p.is_dir()]

    def pull(self, remote_path: str, local_path: Path) -> None:
        self._require_connected("pull")
        src = self._to_local(remote_path)
        if not src.is_file():
            raise ConnectionLostError(f"pull: remote object '{remote_path}' does not exist")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, local_path)

    def pull_dir(self, remote_dir: str, local_dir: Path) -> None:
        self._require_connected("pull_dir")
        src = self._to_local(remote_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return
        for p in src.rglob("*"):
            if p.is_file():
                rel = p.relative_to(src)
                dest = local_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)

    def verify_and_delete(self, remote_path: str, expected_sha256: str, dry_run: bool = False) -> DeletionAttemptResult:
        self._require_connected("verify_and_delete")
        local = self._to_local(remote_path)
        if not local.is_file():
            return DeletionAttemptResult(DeletionOutcome.GONE)
        current_hash = _sha256(local)
        if current_hash != expected_sha256:
            return DeletionAttemptResult(DeletionOutcome.HASH_MISMATCH, current_hash)
        if dry_run:
            return DeletionAttemptResult(DeletionOutcome.WOULD_DELETE)
        local.unlink()
        if local.exists():
            return DeletionAttemptResult(DeletionOutcome.STILL_EXISTS)
        return DeletionAttemptResult(DeletionOutcome.DELETED)
