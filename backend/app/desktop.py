"""Desktop application entry point.

Runs the FastAPI backend on a loopback port and renders the bundled UI in a
native OS window (Edge WebView2 on Windows, WebKitGTK on Linux), so the tool
behaves like an installed program rather than two terminals and a browser tab.

The server still binds to 127.0.0.1 only. This process can delete files from
a connected phone and must never be reachable from the network.
"""
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn

APP_NAME = "Android Backup Manager"

# The window is sized for the tool's dense layout: wide enough for the file
# tree's path and size columns, tall enough to show a useful number of rows.
WINDOW_W, WINDOW_H = 1180, 780
MIN_W, MIN_H = 900, 600

STARTUP_TIMEOUT = 30.0


def _free_port() -> int:
    """Ask the OS for an unused loopback port.

    Not a fixed port: 8420 may already be taken by a dev instance, another
    copy of the app, or something unrelated, and a packaged app cannot ask
    the user to resolve that.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server(uvicorn.Server):
    """uvicorn server that never installs signal handlers.

    It runs on a non-main thread, where signal handling is not available and
    would raise; the window's lifetime is what stops us instead.
    """

    def install_signal_handlers(self) -> None:
        pass


def _wait_until_healthy(base_url: str, timeout: float = STARTUP_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    return False


def main() -> int:
    # Imported here rather than at module scope so that `--help`/`--version`
    # style invocations and error paths don't require a display or GUI stack.
    import webview

    # Imported as an object rather than passed to uvicorn as the import
    # string "app.main:app". A PyInstaller bundle has no importable `app`
    # package on disk for uvicorn's importlib lookup to find, so the string
    # form raises ModuleNotFoundError once frozen. A direct import is also
    # what lets PyInstaller's analysis see the dependency at build time.
    from app.main import app as fastapi_app

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = _Server(config)

    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()

    if not _wait_until_healthy(base_url):
        print(f"{APP_NAME}: backend did not start in time.", file=sys.stderr)
        return 1

    window = webview.create_window(
        APP_NAME,
        base_url,
        width=WINDOW_W,
        height=WINDOW_H,
        min_size=(MIN_W, MIN_H),
    )

    # The update flow needs to be able to close the app from a request
    # handler: on Windows the installer cannot replace files this process
    # holds open. The backend never imports webview itself, so the way to
    # do that is handed to it from here.
    from app.updater import shutdown

    shutdown.register(window.destroy)

    webview.start()

    # webview.start() blocks until the window closes; tell uvicorn to wind
    # down so the process actually exits instead of lingering on the daemon
    # thread.
    server.should_exit = True
    thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
