import asyncio
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.api.jobs import jobs
from app.api.schemas import ConfigUpdateRequest
from app.audit.store import load_history
from app.config import Settings, load_settings, save_settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/history")
def history():
    return list(reversed(load_history()))


@router.get("/config")
def get_config():
    return asdict(load_settings())


@router.put("/config")
def update_config(req: ConfigUpdateRequest):
    current = load_settings()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    new_settings = Settings(**{**asdict(current), **updates})
    save_settings(new_settings)
    return asdict(new_settings)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, since: int = 0):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    events, next_index = job.events_since(since)
    return {"id": job.id, "kind": job.kind, "status": job.status, "events": events,
            "next_index": next_index, "result": job.result, "error": job.error}


@router.websocket("/ws/jobs/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = jobs.get(job_id)
    if not job:
        await websocket.send_json({"error": "job not found"})
        await websocket.close()
        return
    index = 0
    try:
        while True:
            events, index = job.events_since(index)
            for event in events:
                await websocket.send_json({"type": "event", "data": event})
            if job.status != "running":
                await websocket.send_json({"type": "final", "status": job.status,
                                            "result": job.result, "error": job.error})
                break
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
