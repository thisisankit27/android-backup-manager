"""User-editable configuration.

Defaults live here; a user override file (if present) is merged on top.
None of these settings can weaken the mandatory safety checks (manifest-
driven deletion, hash verification, protected-file rules) — they only
affect defaults like where backups go and which categories start checked.
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DATA_DIR = Path.home() / ".android-backup-manager"
CONFIG_PATH = APP_DATA_DIR / "config.json"


@dataclass
class Settings:
    default_backup_parent: str = str(Path.home() / "Desktop")
    default_excluded_report_groups: list[str] = field(default_factory=lambda: ["Disposable"])
    protected_filename_patterns: list[str] = field(
        default_factory=lambda: ["msgstore.db.crypt14", "msgstore-increment-1.db.crypt14"]
    )
    hash_algorithm: str = "sha256"  # fixed; not user-changeable at runtime, exposed for transparency only


def load_settings() -> Settings:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            defaults = asdict(Settings())
            defaults.update({k: v for k, v in data.items() if k in defaults})
            return Settings(**defaults)
        except (json.JSONDecodeError, TypeError):
            return Settings()
    return Settings()


def save_settings(settings: Settings) -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(settings)
    data.pop("hash_algorithm", None)  # not user-editable
    CONFIG_PATH.write_text(json.dumps(data, indent=2))
