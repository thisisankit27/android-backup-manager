from fastapi import APIRouter, HTTPException

from app.adb.real_client import RealAdbClient, check_single_device
from app.api.jobs import jobs
from app.audit.store import load_discovery, save_discovery
from app.discovery.scanner import discover
from app.serialization import discovery_to_dict

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.post("/start")
def start_discovery():
    serial = check_single_device()  # raises HTTPException-friendly AdbError if not connected

    def task(emit):
        emit({"phase": "connecting"})
        client = RealAdbClient(serial)
        emit({"phase": "scanning"})
        result = discover(client, serial)
        disc_id = save_discovery(result)
        emit({"phase": "done", "categories": len(result.categories),
              "files": sum(c.file_count for c in result.categories)})
        return {"discovery_id": disc_id}

    job_id = jobs.start("discovery", task)
    return {"job_id": job_id}


@router.get("/{discovery_id}")
def get_discovery(discovery_id: str):
    try:
        result = load_discovery(discovery_id)
    except FileNotFoundError:
        raise HTTPException(404, "discovery not found")
    return discovery_to_dict(result)
