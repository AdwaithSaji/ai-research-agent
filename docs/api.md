# API Reference

Base URL: `http://localhost:8000` (default).

## `GET /api/health`

Returns `{ status, llm_mode, search_provider }`. `llm_mode` is `"mock"` when
no `OPENAI_API_KEY` is configured.

## `POST /api/research`

Starts a research job in the background and returns immediately.

Request body:

```json
{
  "question": "string, 8-500 chars",
  "depth": "quick | standard | deep",
  "preferred_domains": ["arxiv.org"],
  "excluded_domains": ["pinterest.com"]
}
```

Response: a `ResearchJob` (see `backend/app/models/schemas.py`) with
`stage: "queued"` and no `report` yet.

## `GET /api/research/{job_id}`

Returns the current `ResearchJob`, including `stage`, accumulated `events`,
and `report` once `stage == "done"` (or `error` if `"failed"`).

## `GET /api/research/{job_id}/stream`

Server-Sent Events stream of the same job. Emits `event: progress` for each
stage transition and one final `event: complete` carrying the full
`ResearchJob` (including the report).

## `GET /api/history?limit=20`

Lists recently completed jobs (`id`, `question`, `created_at`) from
persistent storage.
