"""End-to-end smoke test against the actual FastAPI app (mock providers)."""
import time

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["llm_mode"] == "mock"


def test_research_validation_rejects_short_question():
    with TestClient(app) as client:
        resp = client.post("/api/research", json={"question": "short"})
        assert resp.status_code == 422


def test_unknown_job_returns_404():
    with TestClient(app) as client:
        resp = client.get("/api/research/does-not-exist")
        assert resp.status_code == 404


def test_full_research_flow_completes_offline():
    with TestClient(app) as client:
        resp = client.post(
            "/api/research",
            json={"question": "What are common RAG evaluation metrics?", "depth": "quick"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["id"]

        job = None
        for _ in range(60):
            job = client.get(f"/api/research/{job_id}").json()
            if job["stage"] in ("done", "failed"):
                break
            time.sleep(0.5)

        assert job is not None
        assert job["stage"] == "done", job.get("error")
        assert job["report"] is not None
        assert job["usage"]["llm_calls"] > 0
