"""Proves usage.cache_hits (via GatherStats) reflects real cache behavior
instead of being hardcoded to zero."""
import asyncio

import pytest

from app.agent.researcher import gather_sources
from app.config import Settings
from app.models.schemas import ResearchPlan, SubquestionPlan
from app.services.cache import TTLCache
from app.tools.search import MockSearchProvider


@pytest.fixture
def settings() -> Settings:
    return Settings(search_provider="mock", openai_api_key="")


def test_second_run_with_shared_cache_reports_cache_hits(settings):
    plan = ResearchPlan(items=[SubquestionPlan(subquestion="q1", search_queries=["hallucination mitigation"])])
    provider = MockSearchProvider()
    search_cache: TTLCache = TTLCache()
    page_cache: TTLCache = TTLCache()

    async def run_twice():
        first_sources, first_stats = await gather_sources(plan, provider, settings, search_cache, page_cache)
        second_sources, second_stats = await gather_sources(plan, provider, settings, search_cache, page_cache)
        return first_stats, second_stats

    first_stats, second_stats = asyncio.run(run_twice())

    # First run: nothing cached yet, so the search itself is a real call.
    assert first_stats.cache_hits == 0
    assert first_stats.searches_performed >= 1

    # Second run with the SAME query against the SAME caches: the search
    # result and every fetched page should be served from cache.
    assert second_stats.searches_performed == 0
    assert second_stats.cache_hits > 0


def test_fresh_cache_reports_zero_hits(settings):
    plan = ResearchPlan(items=[SubquestionPlan(subquestion="q1", search_queries=["fresh unseen query"])])
    provider = MockSearchProvider()

    async def run():
        return await gather_sources(plan, provider, settings, TTLCache(), TTLCache())

    _, stats = asyncio.run(run())
    assert stats.cache_hits == 0
