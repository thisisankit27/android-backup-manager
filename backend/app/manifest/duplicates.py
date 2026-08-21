"""Hash-based duplicate detection. Never deduplicates — every selected
source file stays in the backup and in the manifest; this only reports
which ones share identical content, so a later viewer knows exactly which
originals map to which content."""
from collections import defaultdict


def find_duplicate_groups(manifest_entries: list[dict]) -> list[dict]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for e in manifest_entries:
        if e.get("verification_status") == "verified" and e.get("source_sha256"):
            by_hash[e["source_sha256"]].append(e["source_path"])
    groups = []
    for i, (sha, paths) in enumerate(sorted(by_hash.items()), start=1):
        if len(paths) > 1:
            groups.append({"group": i, "sha256": sha, "count": len(paths), "paths": paths})
    return groups
