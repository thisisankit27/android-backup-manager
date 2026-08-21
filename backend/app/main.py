"""FastAPI app entrypoint.

Binds to 127.0.0.1 only (see run.py) — this tool operates on personal
device backups and must never be reachable from the network. The browser
never talks to adb directly; every device/filesystem operation goes through
this backend, which owns all the safety checks.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adb.errors import AdbError, AmbiguousDeviceError, ConnectionLostError, NoDeviceError
from app.api.routes_backup import router as backup_router
from app.api.routes_deletion import router as deletion_router
from app.api.routes_device import router as device_router
from app.api.routes_discovery import router as discovery_router
from app.api.routes_meta import router as meta_router

app = FastAPI(title="Android Backup Manager", version="0.1.0")

# Local-only tool: the frontend dev server runs on localhost too, but this
# is not a general-purpose API — CORS is restricted to loopback origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NoDeviceError)
async def no_device_handler(request: Request, exc: NoDeviceError):
    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "no_device"})


@app.exception_handler(AmbiguousDeviceError)
async def ambiguous_device_handler(request: Request, exc: AmbiguousDeviceError):
    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "ambiguous_device"})


@app.exception_handler(ConnectionLostError)
async def connection_lost_handler(request: Request, exc: ConnectionLostError):
    return JSONResponse(status_code=503, content={"detail": str(exc), "error": "connection_lost"})


@app.exception_handler(AdbError)
async def adb_error_handler(request: Request, exc: AdbError):
    return JSONResponse(status_code=502, content={"detail": str(exc), "error": "adb_error"})


app.include_router(device_router)
app.include_router(discovery_router)
app.include_router(backup_router)
app.include_router(deletion_router)
app.include_router(meta_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
