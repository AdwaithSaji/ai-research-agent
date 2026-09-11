import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# Force mock/offline providers for deterministic, cost-free test runs.
os.environ.setdefault("SEARCH_PROVIDER", "mock")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "test_research_agent.db"))

import pytest


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_db():
    yield
    db_path = BACKEND_ROOT / "test_research_agent.db"
    if db_path.exists():
        db_path.unlink()
