"""Researcher stage: runs search queries and fetches/parses source pages.

Bounded and deterministic: a fixed number of queries, a fixed cap on total
sources, bounded fetch concurrency, and per-domain caps for diversity. No LLM
calls happen in this stage — it is pure tool-calling + parsing.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.config import Settings
from app.models.schemas import ResearchPlan, Source
from app.services.cache import TTLCache, normalize_key
from app.services.quality import classify_source_type, score_source_quality
from app.tools.fetch import fetch_and_extract
from app.tools.search import SearchProvider, domain_of

logger = logging.getLogger(__name__)


@dataclass
class GatherStats:
    searches_performed: int = 0  # network search calls actually made (cache misses)
    cache_hits: int = 0  # search + page-fetch results served from cache
    queries_attempted: int = 0
    queries_with_results: int = 0  # queries that returned >=1 usable hit


async def gather_sources(
    plan: ResearchPlan,
    search_provider: SearchProvider,
    settings: Settings,
    search_cache: TTLCache[list],
    page_cache: TTLCache[tuple],
    excluded_domains: list[str] | None = None,
    preferred_domains: list[str] | None = None,
) -> tuple[list[Source], GatherStats]:
    """Returns (sources, stats)."""
    excluded = {d.lower() for d in (excluded_domains or [])}
    preferred = {d.lower() for d in (preferred_domains or [])}

    stats = GatherStats(queries_attempted=len(plan.search_queries))

    # 1. Run searches (deduped queries already guaranteed by planner), cache hits.
    seen_urls: set[str] = set()
    candidates: list[tuple[str, str, str, str]] = []  # (title, url, snippet, query)

    for query in plan.search_queries:
        cache_key = normalize_key(search_provider.name, query)
        cached = search_cache.get(cache_key)
        if cached is not None:
            hits = cached
            stats.cache_hits += 1
        else:
            try:
                hits = await search_provider.search(query, settings.max_results_per_query)
                search_cache.set(cache_key, hits)
                stats.searches_performed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Search failed for query %r: %s", query, exc)
                hits = []

        if hits:
            stats.queries_with_results += 1

        for hit in hits:
            if not hit.url or hit.url in seen_urls:
                continue
            domain = domain_of(hit.url)
            if domain in excluded:
                continue
            seen_urls.add(hit.url)
            candidates.append((hit.title, hit.url, hit.snippet, query))

    # 2. Rank: preferred domains first, then cap per-domain for source diversity.
    def sort_key(c: tuple[str, str, str, str]) -> tuple[int, int]:
        domain = domain_of(c[1])
        return (0 if domain in preferred else 1, 0)

    candidates.sort(key=sort_key)

    domain_counts: dict[str, int] = {}
    selected: list[tuple[str, str, str, str]] = []
    for c in candidates:
        domain = domain_of(c[1])
        if domain_counts.get(domain, 0) >= settings.max_sources_per_domain:
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        selected.append(c)
        if len(selected) >= settings.max_sources_total:
            break

    # 3. Fetch concurrently with a bounded semaphore.
    semaphore = asyncio.Semaphore(settings.request_concurrency)

    async def fetch_one(title: str, url: str, snippet: str, query: str) -> Source:
        domain = domain_of(url)
        cache_key = normalize_key("page", url)
        cached = page_cache.get(cache_key)
        if cached is not None:
            ok, page_title, text, error = cached
            stats.cache_hits += 1
        else:
            async with semaphore:
                result = await fetch_and_extract(url, settings)
            ok, page_title, text, error = result.ok, result.title, result.text, result.error
            page_cache.set(cache_key, (ok, page_title, text, error))

        content = text if ok else ""
        quality = score_source_quality(domain, content or snippet)
        return Source(
            title=(page_title or title or domain),
            url=url,
            domain=domain,
            publisher=domain,
            source_type=classify_source_type(domain),
            snippet=snippet,
            content=content,
            fetch_ok=ok,
            fetch_error=error,
            quality_score=quality,
            query=query,
        )

    sources = await asyncio.gather(*(fetch_one(*c) for c in selected))
    return list(sources), stats


def subquestion_for_query(plan: ResearchPlan, query: str) -> str:
    """Maps a search query back to the subquestion that generated it.

    An exact lookup against the plan's explicit subquestion -> queries[]
    structure (see `ResearchPlan.subquestion_for_query`) — never a positional
    `index % len(subquestions)` guess, which breaks as soon as the number of
    queries and subquestions differ.
    """
    return plan.subquestion_for_query(query)
