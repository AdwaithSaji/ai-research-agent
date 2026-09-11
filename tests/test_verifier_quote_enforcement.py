"""Proves the verifier enforces quote grounding deterministically: an
evidence item with a quote that failed verification must never be treated
as verified evidence downstream, regardless of what the LLM verifier says."""
import asyncio
from typing import Any

from app.agent.verifier import verify_evidence
from app.config import Settings
from app.llm.client import LLMClient
from app.models.schemas import Evidence, Source


class _NoOpVerifierLLM(LLMClient):
    """Flags no conflicts and no unsupported claims — isolates the test to
    the deterministic pre-filter, not the LLM-based checks."""

    async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
        self.usage.calls += 1
        return {"conflicts": [], "unsupported_claim_ids": [], "notes": "no-op"}


def _good_source(source_id: str = "src-1") -> Source:
    return Source(id=source_id, title="T", url="https://example.org/x", domain="example.org", quality_score=0.8)


def _settings() -> Settings:
    return Settings(openai_api_key="")


def test_valid_quoted_evidence_is_kept():
    source = _good_source()
    evidence = [
        Evidence(id="e1", source_id=source.id, subquestion="q", claim="claim one", quote="a real quote", quote_verified=True),
    ]
    result = asyncio.run(verify_evidence(evidence, [source], _NoOpVerifierLLM(), _settings()))
    assert result.kept_evidence_ids == ["e1"]
    assert result.dropped_evidence_ids == []


def test_unverified_quoted_evidence_cannot_be_treated_as_verified():
    source = _good_source()
    evidence = [
        Evidence(id="e1", source_id=source.id, subquestion="q", claim="claim one", quote="a real quote", quote_verified=True),
        Evidence(id="e2", source_id=source.id, subquestion="q", claim="fabricated claim", quote="a quote that was never in the source", quote_verified=False),
    ]
    result = asyncio.run(verify_evidence(evidence, [source], _NoOpVerifierLLM(), _settings()))
    assert "e1" in result.kept_evidence_ids
    assert "e2" not in result.kept_evidence_ids
    assert "e2" in result.dropped_evidence_ids


def test_quote_less_evidence_preserves_existing_behavior():
    # No quote attempted at all (quote="") — this is the mock-LLM/no-quote
    # case, and must NOT be penalized by the quote-grounding check.
    source = _good_source()
    evidence = [
        Evidence(id="e1", source_id=source.id, subquestion="q", claim="claim without a quote", quote="", quote_verified=False),
    ]
    result = asyncio.run(verify_evidence(evidence, [source], _NoOpVerifierLLM(), _settings()))
    assert result.kept_evidence_ids == ["e1"]
    assert result.dropped_evidence_ids == []


def test_existing_quality_floor_and_llm_unsupported_checks_still_work():
    good_source = _good_source("src-good")
    bad_source = Source(id="src-bad", title="T", url="https://example.org/y", domain="example.org", quality_score=0.1)

    class _FlagsOneUnsupportedLLM(LLMClient):
        async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
            self.usage.calls += 1
            return {"conflicts": [], "unsupported_claim_ids": ["e_unsupported"], "notes": ""}

    evidence = [
        Evidence(id="e_kept", source_id=good_source.id, subquestion="q", claim="fine claim", quote="", quote_verified=False),
        Evidence(id="e_low_quality", source_id=bad_source.id, subquestion="q", claim="low quality source claim", quote="", quote_verified=False),
        Evidence(id="e_unsupported", source_id=good_source.id, subquestion="q", claim="speculative claim", quote="", quote_verified=False),
    ]
    result = asyncio.run(verify_evidence(evidence, [good_source, bad_source], _FlagsOneUnsupportedLLM(), _settings()))

    assert result.kept_evidence_ids == ["e_kept"]
    assert "e_low_quality" in result.dropped_evidence_ids
    assert "e_unsupported" in result.dropped_evidence_ids
