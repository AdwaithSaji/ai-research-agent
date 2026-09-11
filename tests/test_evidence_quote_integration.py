"""Integration test: evidence.py must set Evidence.quote_verified using the
deterministic checker, not trust the LLM's own claim about its quote."""
import asyncio
from typing import Any

from app.agent.evidence import extract_evidence
from app.config import Settings
from app.llm.client import LLMClient
from app.models.schemas import ResearchPlan, Source, SubquestionPlan


class _StubEvidenceLLM(LLMClient):
    """Returns one claim with a fixed quote, regardless of input — lets the
    test control exactly what the "evidence analyst" claims to have found."""

    def __init__(self, quote: str) -> None:
        super().__init__()
        self._quote = quote

    async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
        self.usage.calls += 1
        return {"claims": [{"claim": "The source discusses the topic.", "quote": self._quote, "supports_answer": True}]}


def _make_source(content: str) -> Source:
    return Source(
        title="Test Source",
        url="https://example.org/test",
        domain="example.org",
        content=content,
        fetch_ok=True,
        quality_score=0.8,
        relevance_score=0.9,
        query="test query",
    )


def _make_plan() -> ResearchPlan:
    return ResearchPlan(items=[SubquestionPlan(subquestion="What does the source say?", search_queries=["test query"])])


def test_verbatim_quote_is_marked_verified():
    source = _make_source("The system reduces hallucination rates by a wide margin in testing.")
    llm = _StubEvidenceLLM(quote="reduces hallucination rates by a wide margin")
    settings = Settings(openai_api_key="")

    evidence = asyncio.run(extract_evidence([source], _make_plan(), llm, settings))

    assert len(evidence) == 1
    assert evidence[0].quote_verified is True


def test_fabricated_quote_is_marked_unverified():
    source = _make_source("The system reduces hallucination rates by a wide margin in testing.")
    llm = _StubEvidenceLLM(quote="this exact phrase never appears in the source at all")
    settings = Settings(openai_api_key="")

    evidence = asyncio.run(extract_evidence([source], _make_plan(), llm, settings))

    assert len(evidence) == 1
    assert evidence[0].quote_verified is False


def test_empty_quote_is_marked_unverified():
    source = _make_source("Some source content that is long enough to be considered usable text here.")
    llm = _StubEvidenceLLM(quote="")
    settings = Settings(openai_api_key="")

    evidence = asyncio.run(extract_evidence([source], _make_plan(), llm, settings))

    assert len(evidence) == 1
    assert evidence[0].quote_verified is False
