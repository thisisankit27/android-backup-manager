"""Comparing release versions.

Deliberately hand-rolled rather than pulling in `packaging`: this has to
work inside a PyInstaller bundle, where every import is one more thing to
declare and get wrong, and the comparison it needs to do is small.

Handles the three shapes this project actually produces — `0.1.2`, a tag
`v0.1.2`, and a dry-run/prerelease `0.1.2-rc1` — and treats anything it
cannot parse as zeroes rather than raising, because a malformed tag on the
release feed must not break the running app.
"""
import re

#: Digits and letters are keyed separately so `rc10` sorts after `rc9`
#: instead of before it, which a plain string comparison would get wrong.
_TOKEN = re.compile(r"\d+|[A-Za-z]+")


def parse(raw: str) -> tuple[tuple[int, int, int], str]:
    """Split a version into its numeric core and its prerelease suffix."""
    text = (raw or "").strip().lstrip("vV")
    core_text, _, prerelease = text.partition("-")

    parts: list[int] = []
    for chunk in core_text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)

    return (parts[0], parts[1], parts[2]), prerelease


def _prerelease_key(prerelease: str) -> tuple:
    return tuple(
        (0, int(token), "") if token.isdigit() else (1, 0, token.lower())
        for token in _TOKEN.findall(prerelease)
    )


def sort_key(raw: str) -> tuple:
    """Ordering key. `0.1.2` ranks above `0.1.2-rc1`, as it should."""
    core, prerelease = parse(raw)
    if not prerelease:
        return (core, 1, ())
    return (core, 0, _prerelease_key(prerelease))


def is_newer(candidate: str, current: str) -> bool:
    return sort_key(candidate) > sort_key(current)
