"""Single source of truth for the application version.

A source checkout reports ``0.0.0-dev`` rather than impersonating a release.
The release workflow rewrites ``VERSION`` below with the tag being built, so
a packaged build reports the version it was actually built from.

Kept as a plain literal, not read from a file at runtime: PyInstaller would
otherwise need the file bundled and located, and this has to work before
anything else does.
"""

VERSION = "0.0.0-dev"


def is_release_build() -> bool:
    return VERSION != "0.0.0-dev"
