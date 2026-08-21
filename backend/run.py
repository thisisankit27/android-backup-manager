"""Local dev/run entrypoint. Always binds to 127.0.0.1 — never 0.0.0.0 —
since this service can trigger real file deletion on a connected Android
device and must never be reachable from the network."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8420, reload=True)
