"""Core domain types shared across discovery, selection, backup, and deletion.

Centralized here (rather than duplicated per-module) to avoid import cycles
and to keep the selection/manifest contract in exactly one place.
"""
from dataclasses import dataclass, field
from enum import Enum


class FileState(str, Enum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    INACCESSIBLE = "INACCESSIBLE"


class Crypt14Kind(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"


@dataclass
class DiscoveredFile:
    path: str                  # exact remote path
    size: int
    mtime: float
    sha256: str
    category_id: str           # which Category this belongs to
    filename: str
    extension: str
    is_trashed: bool = False
    crypt14_kind: Crypt14Kind | None = None
    default_state: FileState = FileState.INCLUDE


@dataclass
class Category:
    id: str
    label: str
    remote_dir: str
    report_group: str          # Camera / Screenshots / WhatsApp / Downloads / Documents / Other / Disposable
    default_include: bool
    files: list[DiscoveredFile] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)


@dataclass
class InaccessibleLocation:
    path: str
    reason: str


@dataclass
class DiscoveryResult:
    device_serial: str
    generated_at: str
    categories: list[Category]
    inaccessible: list[InaccessibleLocation]

    def all_files(self) -> list[DiscoveredFile]:
        return [f for c in self.categories for f in c.files]


@dataclass
class SelectionEntry:
    """One file's frozen inclusion decision, as of the moment the selection
    was reviewed and frozen. This — not a live directory listing — is the
    sole authority for what backup.py is allowed to copy."""
    path: str
    category_id: str
    state: FileState
    size: int
    sha256_at_selection: str


@dataclass
class SelectionManifest:
    """Frozen output of 'Review Backup'. Immutable once created; backup runs
    reference it by id and never mutate it."""
    id: str
    created_at: str
    device_serial: str
    entries: list[SelectionEntry]

    def included(self) -> list[SelectionEntry]:
        return [e for e in self.entries if e.state == FileState.INCLUDE]


@dataclass
class ManifestFileEntry:
    source_path: str
    backup_path: str
    filename: str
    extension: str
    category: str
    source_size: int | None
    backup_size: int | None
    source_mtime: float | None
    source_sha256: str | None
    backup_sha256: str | None
    copy_status: str            # success | failed
    verification_status: str    # verified | verification_failed | failed
    error: str = ""


@dataclass
class BackupManifest:
    id: str
    created_at: str
    device_serial: str
    backup_dir: str
    selection_manifest_id: str
    entries: list[ManifestFileEntry] = field(default_factory=list)
    manifest_sha256: str | None = None


@dataclass
class DeletionCandidate:
    source_path: str
    backup_path: str
    source_sha256: str
    backup_sha256: str
    size: int
    category: str
    crypt14_kind: Crypt14Kind | None = None


@dataclass
class SkippedCandidate:
    source_path: str
    backup_path: str | None
    reason: str
    detail: str


@dataclass
class DeletionPreview:
    id: str
    created_at: str
    backup_manifest_id: str
    device_serial: str
    eligible: list[DeletionCandidate]
    skipped: list[SkippedCandidate]
    crypt14_inventory: list[dict] = field(default_factory=list)
