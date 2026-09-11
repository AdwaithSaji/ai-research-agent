"""In-memory job registry with per-job async pub/sub for progress streaming.

A research run is bounded and short-lived (seconds to low minutes), so an
in-memory store keyed by job id is sufficient — no need for a distributed
queue. Completed reports are additionally persisted to SQLite (see
`storage.py`) so they survive a server restart.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.models.schemas import ProgressEvent, ResearchJob, Stage


@dataclass
class _JobEntry:
    job: ResearchJob
    subscribers: list[asyncio.Queue] = field(default_factory=list)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, _JobEntry] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: ResearchJob) -> None:
        async with self._lock:
            self._jobs[job.id] = _JobEntry(job=job)

    async def get(self, job_id: str) -> ResearchJob | None:
        entry = self._jobs.get(job_id)
        return entry.job if entry else None

    async def update_stage(self, job_id: str, stage: Stage, message: str, sources_found: int = 0) -> None:
        entry = self._jobs.get(job_id)
        if not entry:
            return
        entry.job.stage = stage
        event = ProgressEvent(stage=stage, message=message, sources_found=sources_found)
        entry.job.events.append(event)
        for q in entry.subscribers:
            q.put_nowait(event)

    async def complete(self, job_id: str, job: ResearchJob) -> None:
        entry = self._jobs.get(job_id)
        if not entry:
            return
        # Preserve the accumulated progress events/created_at from the
        # in-flight job rather than discarding them with the final job object.
        job.events = entry.job.events
        job.created_at = entry.job.created_at
        entry.job = job
        for q in entry.subscribers:
            q.put_nowait(None)  # sentinel: stream end

    async def fail(self, job_id: str, error: str) -> None:
        entry = self._jobs.get(job_id)
        if not entry:
            return
        entry.job.stage = Stage.failed
        entry.job.error = error
        event = ProgressEvent(stage=Stage.failed, message=error)
        entry.job.events.append(event)
        for q in entry.subscribers:
            q.put_nowait(event)
            q.put_nowait(None)

    def subscribe(self, job_id: str) -> asyncio.Queue | None:
        entry = self._jobs.get(job_id)
        if not entry:
            return None
        q: asyncio.Queue = asyncio.Queue()
        entry.subscribers.append(q)
        return q


job_store = JobStore()
