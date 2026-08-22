"""Closing the app from inside a request.

Only the update flow needs this, and only on Windows, where the running
program holds its own files open and the installer cannot replace them
until we are gone.

The GUI layer registers how to close its window; from a source checkout
nothing registers and the fallback applies. Kept in its own module so the
backend never imports webview, which does not exist when the API is being
served to a browser during development.
"""
import os
import threading
import time

_quit_callback = None


def register(callback) -> None:
    """Called by the desktop entry point with a way to close the window."""
    global _quit_callback
    _quit_callback = callback


def has_window() -> bool:
    return _quit_callback is not None


def request_quit(delay: float = 2.0) -> None:
    """Close the app shortly from now.

    Not immediately: the job that asked for this still has a result to
    deliver, and the UI has a message to render before the window goes
    away. A couple of seconds is the difference between "it is updating"
    and the app appearing to crash.
    """
    def run():
        time.sleep(delay)
        if _quit_callback is not None:
            try:
                _quit_callback()
                return
            except Exception:  # noqa: BLE001 — falling through to the hard exit
                pass
        # No window to close, or closing it failed. The installer is
        # already running and is waiting for this process to release its
        # files, so exiting is the point.
        os._exit(0)

    threading.Thread(target=run, name="update-quit", daemon=True).start()
