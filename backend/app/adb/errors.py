class AdbError(RuntimeError):
    """Raised whenever an adb operation fails or the device connection is unhealthy."""


class ConnectionLostError(AdbError):
    """Raised specifically when the device connection is lost mid-operation.

    Callers (backup/deletion engines) must treat this as a hard stop: abort
    the current operation immediately rather than continuing and risking a
    silent 'empty directory' misread of a dropped connection.
    """


class NoDeviceError(AdbError):
    """No authorized device is attached."""


class AmbiguousDeviceError(AdbError):
    """More than one device is attached, or the attached device does not
    match the serial an operation expects (e.g. resuming work against a
    backup that was made from a different phone)."""
