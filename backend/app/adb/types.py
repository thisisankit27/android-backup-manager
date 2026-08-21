from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    manufacturer: str
    model: str
    android_version: str
    sdk: int
    storage_total_bytes: int | None
    storage_used_bytes: int | None
    storage_free_bytes: int | None


@dataclass(frozen=True)
class RemoteEntry:
    """One file as currently observed on the device."""
    path: str
    size: int
    mtime: float
    sha256: str


class DeletionOutcome(str, Enum):
    DELETED = "DELETED"
    WOULD_DELETE = "WOULD_DELETE"
    GONE = "GONE"
    HASH_MISMATCH = "HASH_MISMATCH"
    STILL_EXISTS = "STILL_EXISTS"
    RM_FAILED = "RM_FAILED"


@dataclass(frozen=True)
class DeletionAttemptResult:
    outcome: DeletionOutcome
    observed_sha256: str | None = None
