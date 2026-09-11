"""SQLite persistence for completed research jobs.

Chosen over Postgres/vector storage per project scope: a single research run
produces one JSON-serializable report, queried by id — a key-value table is
sufficient and needs no extra infrastructure to run locally.
"""
from __future__ import annotations

import json

import aiosqlite

from app.models.schemas import ResearchJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_SCHEMA)
            await db.commit()

    async def save_job(self, job: ResearchJob) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO research_jobs (id, question, created_at, payload) VALUES (?, ?, ?, ?)",
                (job.id, job.request.question, job.created_at, job.model_dump_json()),
            )
            await db.commit()

    async def get_job(self, job_id: str) -> ResearchJob | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT payload FROM research_jobs WHERE id = ?", (job_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return ResearchJob.model_validate(json.loads(row[0]))

    async def list_recent(self, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, question, created_at FROM research_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [{"id": r[0], "question": r[1], "created_at": r[2]} for r in rows]
