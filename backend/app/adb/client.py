"""The AdbClient interface.

Every operation that touches the Android device (or, in tests, a fake
sandbox standing in for one) goes through this interface. Business logic
(discovery, backup, deletion) is written against this Protocol only, never
against `subprocess`/`adb` directly — that's what lets the deletion safety
tests run against a fake device instead of a real phone.
"""
from pathlib import Path
from typing import Protocol

from app.adb.types import DeletionAttemptResult, DeviceInfo, RemoteEntry


class AdbClient(Protocol):
    def list_authorized_devices(self) -> list[str]:
        """Return serials of currently authorized/connected devices."""
        ...

    def get_device_info(self, serial: str) -> DeviceInfo:
        ...

    def scan_dir(self, remote_dir: str, max_depth: int | None = 1) -> dict[str, RemoteEntry]:
        """Return every file directly under remote_dir (or recursively, if
        max_depth is None) as {path: RemoteEntry}. Read-only."""
        ...

    def path_exists(self, remote_path: str) -> bool:
        ...

    def list_subdirs(self, remote_dir: str) -> list[str]:
        """Immediate subdirectory names (not full paths) of remote_dir.
        Returns [] if remote_dir doesn't exist. Read-only."""
        ...

    def pull(self, remote_path: str, local_path: Path) -> None:
        """Copy a single file from the device to local_path. Read-only on
        the device side."""
        ...

    def pull_dir(self, remote_dir: str, local_dir: Path) -> None:
        """Recursively copy remote_dir's contents into local_dir. Read-only
        on the device side. (Used for efficient bulk copy; callers are
        responsible for pruning anything locally that wasn't selected.)"""
        ...

    def verify_and_delete(self, remote_path: str, expected_sha256: str, dry_run: bool = False) -> DeletionAttemptResult:
        """Single atomic-as-possible operation: re-hash the file right now,
        delete it ONLY if the hash still matches expected_sha256, and
        confirm it is actually gone afterward. Never deletes on a mismatch.
        With dry_run=True, performs the hash check only (no delete)."""
        ...
