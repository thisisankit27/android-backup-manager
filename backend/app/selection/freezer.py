"""Turns a live discovery + the user's include/exclude choices into an
immutable SelectionManifest. This freeze is the hard boundary the backup
engine operates behind: it never re-queries the device for "what's in this
category now", only ever the exact frozen path list, so a file created after
this point (e.g. a new photo taken during the review step) can never sneak
into a backup.
"""
from app.audit.store import new_id, save_selection
from app.models import DiscoveryResult, FileState, SelectionEntry, SelectionManifest
import datetime


def freeze_selection(discovery: DiscoveryResult, overrides: dict[str, str]) -> SelectionManifest:
    """overrides: {path: "INCLUDE"|"EXCLUDE"} for files whose state differs
    from their category default. Files not mentioned keep their default
    state from discovery. INACCESSIBLE files always stay INACCESSIBLE."""
    entries: list[SelectionEntry] = []
    for category in discovery.categories:
        for f in category.files:
            if f.default_state == FileState.INACCESSIBLE:
                state = FileState.INACCESSIBLE
            else:
                override = overrides.get(f.path)
                state = FileState(override) if override else f.default_state
            entries.append(SelectionEntry(
                path=f.path, category_id=category.id, state=state,
                size=f.size, sha256_at_selection=f.sha256,
            ))

    manifest = SelectionManifest(
        id=new_id("sel"),
        created_at=datetime.datetime.now().isoformat(timespec="seconds"),
        device_serial=discovery.device_serial,
        entries=entries,
    )
    save_selection(manifest)
    return manifest
