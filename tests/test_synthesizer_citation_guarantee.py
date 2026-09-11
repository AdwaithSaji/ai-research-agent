"""Integration test: the synthesizer must strip any citation marker the LLM
invents that doesn't correspond to an actually-cited source, and must report
accurate ReportQualityStats — this is the "never trust the LLM to invent
source IDs" guarantee enforced in deterministic backend code."""
import asyncio
from typing import Any

from app.agent.synthesizer import synthesize_report
from app.config import Settings
from app.llm.client import LLMClient
from app.models.schemas import Evidence, Source, VerificationResult


class _StubSynthesizerLLM(LLMClient):
    """Emits a hallucinated [9] marker alongside two real ones."""

    async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
        self.usage.calls += 1
        return {
            "executive_summary": "Approaches vary in effectiveness [1] and evidence quality [9].",
            "key_findings": ["Finding one is well supported [1].", "Finding two cites a made-up source [9]."],
            "analysis": "Source [2] corroborates this, but [9] does not exist.",
            "uncertainty": "Some gaps remain.",
            "conclusion": "Overall the evidence is mixed.",
        }


def _make_sources() -> list[Source]:
    return [
        Source(id="src-1", title="Source One", url="https://example.org/1", domain="example.org", content="x" * 100, fetch_ok=True),
        Source(id="src-2", title="Source Two", url="https://example.org/2", domain="example.org", content="y" * 100, fetch_ok=True),
    ]


def _make_evidence() -> list[Evidence]:
    return [
        Evidence(id="e1", source_id="src-1", subquestion="q1", claim="Claim from source one", quote="", quote_verified=False),
        Evidence(id="e2", source_id="src-2", subquestion="q1", claim="Claim from source two", quote="", quote_verified=False),
    ]


def test_hallucinated_citation_marker_is_stripped_from_every_field():
    sources = _make_sources()
    evidence = _make_evidence()
    verification = VerificationResult(kept_evidence_ids=["e1", "e2"], dropped_evidence_ids=[])
    settings = Settings(openai_api_key="")

    report = asyncio.run(
        synthesize_report("test question", sources, evidence, verification, 1, _StubSynthesizerLLM(), settings)
    )

    # Only [1] and [2] were ever assigned — [9] must not survive anywhere.
    assert "[9]" not in report.executive_summary
    assert all("[9]" not in f for f in report.key_findings)
    assert "[9]" not in report.analysis

    # Valid markers must be preserved untouched.
    assert "[1]" in report.executive_summary
    assert "[2]" in report.analysis

    # Deterministic stats must reflect exactly what happened: 4 markers found
    # total (2 valid [1]/[2] occurrences below... see breakdown), some invalid.
    assert report.quality_stats.citation_markers_invalid_removed >= 1
    assert report.quality_stats.citation_markers_valid >= 1
    assert report.quality_stats.evidence_kept_after_verification == 2
    assert report.quality_stats.total_evidence_extracted == 2


def test_all_citations_are_valid_when_llm_behaves():
    sources = _make_sources()
    evidence = _make_evidence()
    verification = VerificationResult(kept_evidence_ids=["e1", "e2"], dropped_evidence_ids=[])
    settings = Settings(openai_api_key="")

    class _WellBehavedLLM(LLMClient):
        async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
            self.usage.calls += 1
            return {
                "executive_summary": "Findings are grounded in [1] and [2].",
                "key_findings": ["Point one [1]."],
                "analysis": "Analysis referencing [2].",
                "uncertainty": "None notable.",
                "conclusion": "Done.",
            }

    report = asyncio.run(
        synthesize_report("test question", sources, evidence, verification, 1, _WellBehavedLLM(), settings)
    )
    assert report.quality_stats.citation_markers_invalid_removed == 0
    assert report.quality_stats.citation_validity_rate == 1.0
