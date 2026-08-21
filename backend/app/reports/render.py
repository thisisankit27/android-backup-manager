"""Human-readable (txt + html) report rendering. Pure functions: given
already-computed data, produce text. No I/O, no adb calls here — callers
decide where to save the output."""
from collections import defaultdict


def _wrap_html(title: str, body_text: str) -> str:
    escaped = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f"<html><head><meta charset='utf-8'><title>{title}</title>"
        "<style>body{font-family:ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap;"
        "padding:2em;max-width:1100px;margin:auto;line-height:1.4;}</style>"
        f"</head><body>{escaped}</body></html>"
    )


def render_discovery_report(discovery_dict: dict) -> tuple[str, str]:
    lines = ["=" * 79, "DISCOVERY REPORT (read-only)", "=" * 79,
             f"Device: {discovery_dict['device_serial']}", f"Generated: {discovery_dict['generated_at']}", ""]
    for cat in discovery_dict["categories"]:
        size_mb = sum(f["size"] for f in cat["files"]) / (1024 ** 2)
        lines.append(f"  {cat['label']:40s} files={len(cat['files']):6d}  size={size_mb:9.2f} MB  "
                     f"group={cat['report_group']:10s} default_include={cat['default_include']}")
    lines.append("")
    lines.append("INACCESSIBLE LOCATIONS")
    for loc in discovery_dict["inaccessible"]:
        lines.append(f"  {loc['path']}: {loc['reason']}")
    if not discovery_dict["inaccessible"]:
        lines.append("  None.")
    txt = "\n".join(lines)
    return txt, _wrap_html("Discovery Report", txt)


def render_backup_report(manifest_entries: list[dict], device_serial: str, backup_dir: str,
                          duplicate_groups: list[dict]) -> tuple[str, str]:
    by_cat = defaultdict(lambda: {"count": 0, "size": 0, "ok": 0, "failed": 0})
    for e in manifest_entries:
        c = by_cat[e["category"]]
        c["count"] += 1
        c["size"] += e.get("backup_size") or 0
        if e["verification_status"] == "verified":
            c["ok"] += 1
        else:
            c["failed"] += 1

    total = len(manifest_entries)
    total_ok = sum(1 for e in manifest_entries if e["verification_status"] == "verified")
    total_size = sum(e.get("backup_size") or 0 for e in manifest_entries if e["verification_status"] == "verified")

    lines = ["=" * 79, "BACKUP REPORT", "=" * 79,
              f"Device: {device_serial}", f"Backup destination: {backup_dir}",
              f"Total files considered: {total}", f"Successfully verified: {total_ok}",
              f"Failed: {total - total_ok}", f"Total verified size: {total_size / (1024**3):.2f} GB", ""]
    lines.append("BY CATEGORY")
    for cat, c in sorted(by_cat.items()):
        lines.append(f"  {cat:20s} files={c['count']:6d} verified={c['ok']:6d} failed={c['failed']:4d} "
                     f"size={c['size']/(1024**2):.1f} MB")
    lines.append("")
    lines.append("PROBLEMS")
    failed = [e for e in manifest_entries if e["verification_status"] != "verified"]
    if not failed:
        lines.append("  None.")
    else:
        for e in failed:
            lines.append(f"  FAILED: {e['source_path']} ({e['error']})")
    lines.append("")
    lines.append(f"DUPLICATE GROUPS: {len(duplicate_groups)}")
    for g in duplicate_groups:
        lines.append(f"  Group #{g['group']}: {g['count']} files, sha256 {g['sha256'][:16]}...")
        for p in g["paths"]:
            lines.append(f"    - {p}")
    txt = "\n".join(lines)
    return txt, _wrap_html("Backup Report", txt)


def render_deletion_preview_report(preview_dict: dict) -> tuple[str, str]:
    eligible = preview_dict["eligible"]
    skipped = preview_dict["skipped"]
    by_reason = defaultdict(lambda: {"count": 0, "size": 0})
    for s in skipped:
        r = by_reason[s["reason"]]
        r["count"] += 1

    lines = ["=" * 79, "DELETION PREVIEW — READ ONLY, NO FILES DELETED", "=" * 79,
              f"Device: {preview_dict['device_serial']}", f"Generated: {preview_dict['created_at']}", "",
              f"Eligible: {len(eligible)} files, {sum(c['size'] for c in eligible)/(1024**3):.2f} GB",
              f"Skipped: {len(skipped)} files", ""]
    lines.append("SKIP REASONS")
    for reason, r in sorted(by_reason.items()):
        lines.append(f"  {reason:28s} count={r['count']}")
    lines.append("")
    lines.append("WHATSAPP .crypt14 INVENTORY")
    for c in preview_dict.get("crypt14_inventory", []):
        verdict = "ELIGIBLE" if c["eligible"] else f"PROTECTED ({c['reason']})"
        lines.append(f"  [{c['kind'].upper():10s}] {c['filename']:50s} {verdict}")
    txt = "\n".join(lines)
    return txt, _wrap_html("Deletion Preview", txt)


def render_deletion_report(summary: dict) -> tuple[str, str]:
    lines = ["=" * 79, "DELETION REPORT", "=" * 79,
              f"Generated: {summary.get('generated_at')}", f"Backup dir: {summary.get('backup_dir')}", ""]
    if summary.get("aborted_reason"):
        lines.append(f"*** STOPPED EARLY: {summary['aborted_reason']} ***")
        lines.append("")
    lines.append(f"Deleted: {summary.get('deleted_count')} files, "
                 f"{(summary.get('deleted_size') or 0) / (1024**3):.2f} GB")
    lines.append(f"Skipped: {summary.get('skipped_count')} files")
    txt = "\n".join(lines)
    return txt, _wrap_html("Deletion Report", txt)
