"""In-process background job runner for long operations (discovery, backup,
deletion preview, deletion execution). Each job runs in its own thread
(adb/subprocess calls are blocking, so a thread is simpler and safer here
than bolting them onto the asyncio loop) and appends progress events to a
list that both polling (GET /api/jobs/{id}) and the WebSocket endpoint can
read.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"  # running | done | error
    events: list[dict] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def emit(self, event: dict) -> None:
        with self._lock:
            self.events.append(event)

    def events_since(self, index: int) -> tuple[list[dict], int]:
        with self._lock:
            return list(self.events[index:]), len(self.events)


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, fn: Callable[[Callable[[dict], None]], Any]) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, kind=kind)
        with self._lock:
            self._jobs[job_id] = job

        def runner():
            try:
                result = fn(job.emit)
                job.result = result
                job.status = "done"
            except Exception as e:  # noqa: BLE001 — surfaced to the API caller, not swallowed
                job.error = str(e)
                job.status = "error"

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active_kinds(self, exclude: tuple[str, ...] = ()) -> list[str]:
        """Kinds of job currently running.

        Used to refuse an update while real work is in flight: this app
        deletes photos, and a new version must never arrive underneath a
        backup or a deletion that is halfway done.
        """
        with self._lock:
            return sorted(
                {j.kind for j in self._jobs.values() if j.status == "running" and j.kind not in exclude}
            )


jobs = JobManager()
