"""HTTPS fetching with the host pinned across redirects.

`urllib` follows redirects on its own, so checking the URL you passed in
proves nothing about where the bytes came from. GitHub relies on redirects
for exactly the request that matters most here — an asset download hops
from github.com to objects.githubusercontent.com — so the check has to
happen on every hop, not just the first.
"""
import urllib.error
import urllib.request
from urllib.parse import urlparse

USER_AGENT = "android-backup-manager"


class UnsafeUrlError(Exception):
    """A URL was not HTTPS, or pointed somewhere we do not fetch from."""


def assert_allowed(url: str, allowed_hosts: tuple[str, ...]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsafeUrlError(f"refusing to fetch over {parsed.scheme or 'no'} scheme: {url!r}")
    if parsed.hostname not in allowed_hosts:
        raise UnsafeUrlError(f"refusing to fetch from host {parsed.hostname!r}")


class _PinnedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: tuple[str, ...]):
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        assert_allowed(newurl, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def opener(allowed_hosts: tuple[str, ...]) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_PinnedRedirectHandler(allowed_hosts))


def fetch(url: str, allowed_hosts: tuple[str, ...], timeout: float = 15.0,
          accept: str | None = None) -> bytes:
    """Fetch a URL whose every hop stays inside `allowed_hosts`."""
    assert_allowed(url, allowed_hosts)
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with opener(allowed_hosts).open(request, timeout=timeout) as response:
        return response.read()
