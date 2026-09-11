"""Full pipeline integration test using mock LLM + mock search providers.

Exercises Planner -> Researcher -> Evidence Analyst -> Verifier -> Synthesizer
end-to-end with zero LLM cost and no real search API calls, and asserts the
citation-grounding invariant: every citation must point at a real,
actually-retrieved source (never a fabricated one). Page *fetching* still
hits the real network for whatever URLs the mock search returns (example.org),
so it also exercises real fetch-failure handling.
"""
import asyncio

import pytest

from app.agent.evidence import extract_evidence
from app.agent.planner import plan_research
from app.agent.researcher import gather_sources
from app.agent.synthesizer import synthesize_report
from app.agent.verifier import verify_evidence
from app.config import Settings
from app.llm.client import MockLLMClient
from app.models.schemas import ResearchDepth
from app.services.cache import TTLCache
from app.tools.search import MockSearchProvider


@pytest.fixture
def settings() -> Settings:
    return Settings(search_provider="mock", openai_api_key="")


def test_full_pipeline_runs_offline_and_grounds_citations(settings):
    async def run():
        llm = MockLLMClient()
        search_provider = MockSearchProvider()
        plan = await plan_research(
            "Compare approaches for reducing hallucinations in LLMs", ResearchDepth.quick, llm, settings
        )
        assert plan.subquestions
        assert plan.search_queries

        sources, searches_performed = await gather_sources(
            plan, search_provider, settings, TTLCache(), TTLCache()
        )
        assert searches_performed > 0
        assert len(sources) > 0
        # MockSearchProvider returns example.org URLs: the real fetch step still
        # runs against them (this test is offline for search/LLM, not fetch), so
        # fetch may legitimately fail (e.g. no extractable content) — the
        # pipeline must handle that gracefully rather than assuming success.
        assert all(isinstance(s.fetch_ok, bool) for s in sources)

        evidence = await extract_evidence(sources, plan, llm, settings)
        verification = await verify_evidence(evidence, sources, llm, settings)
        report = await synthesize_report(
            "Compare approaches for reducing hallucinations in LLMs",
            sources,
            evidence,
            verification,
            len(plan.search_queries),
            llm,
            settings,
        )
        return sources, evidence, report

    sources, evidence, report = asyncio.run(run())

    source_ids = {s.id for s in sources}
    # Every citation must map to a source that was actually retrieved.
    for citation in report.citations:
        assert citation.source_id in source_ids
    # Every source attached to the report must be one of the retrieved sources.
    for s in report.sources:
        assert s.id in source_ids

    assert report.question
    assert report.methodology
    assert isinstance(report.insufficient_evidence, bool)


def test_insufficient_evidence_flag_when_no_sources(settings):
    from app.models.schemas import ResearchPlan, VerificationResult

    async def run():
        llm = MockLLMClient()
        plan = ResearchPlan(subquestions=["q1"], search_queries=["q1"])
        verification = VerificationResult(kept_evidence_ids=[], dropped_evidence_ids=[])
        return await synthesize_report("test question", [], [], verification, 1, llm, settings)

    report = asyncio.run(run())
    assert report.insufficient_evidence is True
    assert report.sources == []
    assert report.citations == []
