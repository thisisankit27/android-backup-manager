from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.adb.errors import AdbError
from app.adb.real_client import RealAdbClient, check_single_device
from app.audit.store import load_history

router = APIRouter(prefix="/api/device", tags=["device"])


@router.get("/status")
def device_status():
    try:
        serial = check_single_device()
    except AdbError as e:
        return {"connected": False, "reason": str(e)}

    client = RealAdbClient(serial)
    try:
        info = client.get_device_info(serial)
    except AdbError as e:
        return {"connected": False, "reason": f"connected but failed to read device info: {e}"}

    history = load_history()
    last_backup = next((h for h in reversed(history) if h["type"] == "backup"), None)
    last_deletion_preview = next((h for h in reversed(history) if h["type"] == "deletion_preview"), None)
    last_deletion = next((h for h in reversed(history) if h["type"] == "deletion"), None)

    return {
        "connected": True,
        "device": asdict(info),
        "last_backup": last_backup,
        "last_deletion_preview": last_deletion_preview,
        "last_deletion": last_deletion,
    }
