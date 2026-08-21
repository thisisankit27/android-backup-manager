from pydantic import BaseModel


class FreezeSelectionRequest(BaseModel):
    discovery_id: str
    overrides: dict[str, str] = {}  # path -> "INCLUDE" | "EXCLUDE"


class StartBackupRequest(BaseModel):
    selection_id: str
    dest_parent: str | None = None


class StartDeletionPreviewRequest(BaseModel):
    backup_dir: str


class ExecuteDeletionRequest(BaseModel):
    backup_dir: str
    preview_id: str
    confirmation_phrase: str
    preview_acknowledged: bool
    dry_run: bool = False


class ConfigUpdateRequest(BaseModel):
    default_backup_parent: str | None = None
    default_excluded_report_groups: list[str] | None = None
    protected_filename_patterns: list[str] | None = None
