"""Read-only discovery engine.

Walks the device's accessible user storage through an AdbClient, classifies
files into categories, and reports inaccessible locations (Android/data/*)
without ever implying their contents were seen. Performs no writes, no
deletes, no modification of any kind on the device — every AdbClient method
it calls is read-only (scan_dir, list_subdirs, path_exists).
"""
import datetime
import os

from app.adb.client import AdbClient
from app.discovery.classify import (
    DISPOSABLE_DIRNAMES,
    KNOWN_TOP_LEVEL_DIRS,
    STORAGE_ROOT,
    WHATSAPP_BACKUPS_ROOT,
    WHATSAPP_DATABASES_ROOT,
    WHATSAPP_MEDIA_ROOT,
    WHATSAPP_MEDIA_SUBFOLDERS,
    classify_crypt14,
    extension_of,
    is_trashed,
)
from app.models import Category, DiscoveredFile, DiscoveryResult, FileState, InaccessibleLocation


def _build_category(client: AdbClient, cat_id: str, label: str, remote_dir: str,
                     report_group: str, default_include: bool) -> Category | None:
    entries = client.scan_dir(remote_dir, max_depth=None)
    if not entries:
        return None
    category = Category(id=cat_id, label=label, remote_dir=remote_dir,
                         report_group=report_group, default_include=default_include)
    for path, entry in entries.items():
        filename = os.path.basename(path)
        trashed = is_trashed(filename)
        crypt14_kind = classify_crypt14(filename)
        state = FileState.INCLUDE if default_include else FileState.EXCLUDE
        if trashed:
            state = FileState.EXCLUDE
        if crypt14_kind is not None and crypt14_kind.value == "current":
            # current DB can still be *backed up* by explicit choice, but never defaults to included-for-deletion later;
            # for backup selection it's reasonable to default it to included like the rest of WhatsApp.
            pass
        category.files.append(DiscoveredFile(
            path=path, size=entry.size, mtime=entry.mtime, sha256=entry.sha256,
            category_id=cat_id, filename=filename, extension=extension_of(filename),
            is_trashed=trashed, crypt14_kind=crypt14_kind, default_state=state,
        ))
    return category


def _discover_whatsapp(client: AdbClient) -> list[Category]:
    categories: list[Category] = []
    for subfolder in client.list_subdirs(WHATSAPP_MEDIA_ROOT):
        group, default_include = WHATSAPP_MEDIA_SUBFOLDERS.get(subfolder, ("Other", True))
        cat_id = "wa_" + subfolder.lower().replace(" ", "_").replace(".", "")
        cat = _build_category(client, cat_id, f"WhatsApp / {subfolder}",
                               f"{WHATSAPP_MEDIA_ROOT}/{subfolder}", group, default_include)
        if cat:
            categories.append(cat)

    db_cat = _build_category(client, "wa_databases", "WhatsApp / Databases",
                              WHATSAPP_DATABASES_ROOT, "WhatsApp", True)
    if db_cat:
        categories.append(db_cat)

    for subfolder in client.list_subdirs(WHATSAPP_BACKUPS_ROOT):
        cat_id = "wa_backups_" + subfolder.lower().replace(" ", "_")
        cat = _build_category(client, cat_id, f"WhatsApp / Backups / {subfolder}",
                               f"{WHATSAPP_BACKUPS_ROOT}/{subfolder}", "Disposable", False)
        if cat:
            categories.append(cat)
    return categories


def _discover_dcim(client: AdbClient) -> list[Category]:
    categories = []
    dcim_root = f"{STORAGE_ROOT}/DCIM"
    for subfolder in client.list_subdirs(dcim_root):
        if subfolder in DISPOSABLE_DIRNAMES:
            continue
        remote_dir = f"{dcim_root}/{subfolder}"
        if subfolder == "Camera":
            cat_id, label, group, default_include = "camera", "Camera", "Camera", True
        elif subfolder == "WhatsApp":
            cat_id, label, group, default_include = "legacy_whatsapp_dcim", "WhatsApp (legacy DCIM)", "WhatsApp", True
        else:
            cat_id = "dcim_" + subfolder.lower().replace(" ", "_")
            label, group, default_include = f"DCIM / {subfolder}", "Camera", True
        cat = _build_category(client, cat_id, label, remote_dir, group, default_include)
        if cat:
            categories.append(cat)
    return categories


def _discover_pictures(client: AdbClient) -> list[Category]:
    categories = []
    root = f"{STORAGE_ROOT}/Pictures"
    for subfolder in client.list_subdirs(root):
        if subfolder in DISPOSABLE_DIRNAMES:
            continue
        remote_dir = f"{root}/{subfolder}"
        if subfolder == "Screenshots":
            cat_id, label, group, default_include = "screenshots", "Screenshots", "Screenshots", True
        elif subfolder == "WhatsApp":
            cat_id, label, group, default_include = "legacy_whatsapp_pictures", "WhatsApp (legacy Pictures)", "WhatsApp", True
        else:
            cat_id = "pictures_" + subfolder.lower().replace(" ", "_")
            label, group, default_include = f"Pictures / {subfolder}", "Other", True
        cat = _build_category(client, cat_id, label, remote_dir, group, default_include)
        if cat:
            categories.append(cat)
    return categories


def _discover_movies(client: AdbClient) -> list[Category]:
    categories = []
    root = f"{STORAGE_ROOT}/Movies"
    for subfolder in client.list_subdirs(root):
        if subfolder in DISPOSABLE_DIRNAMES:
            continue
        remote_dir = f"{root}/{subfolder}"
        if subfolder == "WhatsApp":
            cat_id, label, group, default_include = "legacy_whatsapp_movies", "WhatsApp (legacy Movies)", "WhatsApp", True
        else:
            cat_id = "movies_" + subfolder.lower().replace(" ", "_")
            label, group, default_include = f"Movies / {subfolder}", "Other", True
        cat = _build_category(client, cat_id, label, remote_dir, group, default_include)
        if cat:
            categories.append(cat)
    return categories


def _discover_custom_top_level(client: AdbClient) -> list[Category]:
    """Any top-level user-created folder that isn't an OS/vendor system dir
    (e.g. a device-specific personal folder). Kept generic on purpose so the
    app works on phones with different personal folder layouts."""
    categories = []
    for name in client.list_subdirs(STORAGE_ROOT):
        if name in KNOWN_TOP_LEVEL_DIRS or name.startswith("."):
            continue
        cat_id = "custom_" + name.lower().replace(" ", "_")
        cat = _build_category(client, cat_id, name, f"{STORAGE_ROOT}/{name}", "Other", True)
        if cat:
            categories.append(cat)
    return categories


def _discover_fixed_roots(client: AdbClient) -> list[Category]:
    categories = []
    for cat_id, label, remote_dir, group in [
        ("download", "Downloads", f"{STORAGE_ROOT}/Download", "Downloads"),
        ("documents", "Documents", f"{STORAGE_ROOT}/Documents", "Documents"),
    ]:
        cat = _build_category(client, cat_id, label, remote_dir, group, True)
        if cat:
            categories.append(cat)
    return categories


def _discover_inaccessible(client: AdbClient) -> list[InaccessibleLocation]:
    inaccessible = []
    android_data = f"{STORAGE_ROOT}/Android/data"
    packages = client.list_subdirs(android_data)
    if packages:
        inaccessible.append(InaccessibleLocation(
            path=android_data,
            reason=(f"{len(packages)} app-private folder(s) visible by name only "
                    f"(e.g. {', '.join(packages[:3])}{', ...' if len(packages) > 3 else ''}); "
                    "file contents cannot be read due to Android 11+ scoped-storage "
                    "sandboxing. If any app stores personal content only here, it will "
                    "NOT be backed up."),
        ))
    return inaccessible


def discover(client: AdbClient, device_serial: str) -> DiscoveryResult:
    categories: list[Category] = []
    categories += _discover_dcim(client)
    categories += _discover_pictures(client)
    categories += _discover_movies(client)
    categories += _discover_fixed_roots(client)
    categories += _discover_custom_top_level(client)
    categories += _discover_whatsapp(client)

    return DiscoveryResult(
        device_serial=device_serial,
        generated_at=datetime.datetime.now().isoformat(timespec="seconds"),
        categories=categories,
        inaccessible=_discover_inaccessible(client),
    )
