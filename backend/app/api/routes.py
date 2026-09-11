"""HTTP API surface.

Kept intentionally small: create a research job, stream its progress, fetch
its result. All heavy lifting lives in the orchestrator/agent modules.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.orchestrator import run_research_job
from app.config import get_settings
from app.llm.client import build_llm_client
from app.models.schemas import ResearchJob, ResearchRequest, Stage
from app.services.jobs import job_store
from app.services.storage import Storage
from app.tools.search import build_search_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_settings = get_settings()
_storage = Storage(_settings.database_path)


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "llm_mode": "live" if _settings.openai_api_key else "mock",
        "search_provider": build_search_provider(_settings).name,
    }


@router.post("/research", response_model=ResearchJob)
async def start_research(request: ResearchRequest) -> ResearchJob:
    job = ResearchJob(request=request, stage=Stage.queued)
    await job_store.create(job)

    llm = build_llm_client(_settings)
    search_provider = build_search_provider(_settings)

    asyncio.create_task(
        run_research_job(job.id, request, llm, search_provider, _settings, job_store, _storage)
    )
    return job


@router.get("/research/{job_id}", response_model=ResearchJob)
async def get_research(job_id: str) -> ResearchJob:
    job = await job_store.get(job_id)
    if job is None:
        job = await _storage.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job


@router.get("/research/{job_id}/stream")
async def stream_research(job_id: str, request: Request):
    queue = job_store.subscribe(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Research job not found")

    async def event_generator():
        job = await job_store.get(job_id)
        if job:
            for event in job.events:
                yield {"event": "progress", "data": event.model_dump_json()}
            if job.stage in (Stage.done, Stage.failed):
                yield {"event": "complete", "data": job.model_dump_json()}
                return

        while True:
            if await request.is_disconnected():
                break
            item = await queue.get()
            if item is None:
                job = await job_store.get(job_id)
                if job:
                    yield {"event": "complete", "data": job.model_dump_json()}
                break
            yield {"event": "progress", "data": item.model_dump_json()}

    return EventSourceResponse(event_generator())


@router.get("/history")
async def history(limit: int = 20) -> list[dict]:
    return await _storage.list_recent(limit)
