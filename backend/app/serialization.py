"""Explicit (not reflection-based) to/from-dict conversion for the domain
models that need to survive a JSON round trip. Kept explicit so enum fields
and nested lists are handled correctly and predictably.
"""
from app.models import (
    Category,
    Crypt14Kind,
    DiscoveredFile,
    DiscoveryResult,
    FileState,
    InaccessibleLocation,
    SelectionEntry,
    SelectionManifest,
)


def file_to_dict(f: DiscoveredFile) -> dict:
    return {
        "path": f.path, "size": f.size, "mtime": f.mtime, "sha256": f.sha256,
        "category_id": f.category_id, "filename": f.filename, "extension": f.extension,
        "is_trashed": f.is_trashed,
        "crypt14_kind": f.crypt14_kind.value if f.crypt14_kind else None,
        "default_state": f.default_state.value,
    }


def file_from_dict(d: dict) -> DiscoveredFile:
    return DiscoveredFile(
        path=d["path"], size=d["size"], mtime=d["mtime"], sha256=d["sha256"],
        category_id=d["category_id"], filename=d["filename"], extension=d["extension"],
        is_trashed=d["is_trashed"],
        crypt14_kind=Crypt14Kind(d["crypt14_kind"]) if d.get("crypt14_kind") else None,
        default_state=FileState(d["default_state"]),
    )


def category_to_dict(c: Category) -> dict:
    return {
        "id": c.id, "label": c.label, "remote_dir": c.remote_dir,
        "report_group": c.report_group, "default_include": c.default_include,
        "files": [file_to_dict(f) for f in c.files],
    }


def category_from_dict(d: dict) -> Category:
    return Category(
        id=d["id"], label=d["label"], remote_dir=d["remote_dir"],
        report_group=d["report_group"], default_include=d["default_include"],
        files=[file_from_dict(f) for f in d["files"]],
    )


def discovery_to_dict(r: DiscoveryResult) -> dict:
    return {
        "device_serial": r.device_serial, "generated_at": r.generated_at,
        "categories": [category_to_dict(c) for c in r.categories],
        "inaccessible": [{"path": i.path, "reason": i.reason} for i in r.inaccessible],
    }


def discovery_from_dict(d: dict) -> DiscoveryResult:
    return DiscoveryResult(
        device_serial=d["device_serial"], generated_at=d["generated_at"],
        categories=[category_from_dict(c) for c in d["categories"]],
        inaccessible=[InaccessibleLocation(**i) for i in d["inaccessible"]],
    )


def selection_to_dict(s: SelectionManifest) -> dict:
    return {
        "id": s.id, "created_at": s.created_at, "device_serial": s.device_serial,
        "entries": [
            {"path": e.path, "category_id": e.category_id, "state": e.state.value,
             "size": e.size, "sha256_at_selection": e.sha256_at_selection}
            for e in s.entries
        ],
    }


def selection_from_dict(d: dict) -> SelectionManifest:
    return SelectionManifest(
        id=d["id"], created_at=d["created_at"], device_serial=d["device_serial"],
        entries=[
            SelectionEntry(path=e["path"], category_id=e["category_id"], state=FileState(e["state"]),
                            size=e["size"], sha256_at_selection=e["sha256_at_selection"])
            for e in d["entries"]
        ],
    )
