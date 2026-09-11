"""Research Orchestrator: runs the bounded pipeline stage-by-stage, reporting
progress and tracking usage. This is the only place that sequences stages —
each stage module is a plain function with explicit input/output types, so
there is no uncontrolled autonomous loop, just a fixed pipeline:

    Planner -> Researcher -> Evidence Analyst -> Verifier -> Synthesizer
"""
from __future__ import annotations

import logging
import time

from app.agent.evidence import extract_evidence
from app.agent.planner import plan_research
from app.agent.researcher import gather_sources
from app.agent.synthesizer import synthesize_report
from app.agent.verifier import verify_evidence
from app.config import Settings
from app.llm.client import LLMClient
from app.models.schemas import ResearchJob, ResearchRequest, Stage, UsageStats
from app.services.cache import TTLCache
from app.services.jobs import JobStore
from app.services.storage import Storage
from app.tools.search import SearchProvider

logger = logging.getLogger(__name__)

# Process-lifetime caches shared across research runs (dedup across requests).
_search_cache: TTLCache = TTLCache(ttl_seconds=3600)
_page_cache: TTLCache = TTLCache(ttl_seconds=3600)


async def run_research_job(
    job_id: str,
    request: ResearchRequest,
    llm: LLMClient,
    search_provider: SearchProvider,
    settings: Settings,
    job_store: JobStore,
    storage: Storage,
) -> None:
    start = time.monotonic()
    try:
        await job_store.update_stage(job_id, Stage.planning, "Decomposing question into subquestions...")
        plan = await plan_research(request.question, request.depth, llm, settings)

        await job_store.update_stage(
            job_id, Stage.searching, f"Searching {len(plan.search_queries)} quer(y/ies)..."
        )
        sources, gather_stats = await gather_sources(
            plan,
            search_provider,
            settings,
            _search_cache,
            _page_cache,
            excluded_domains=request.excluded_domains,
            preferred_domains=request.preferred_domains,
        )
        await job_store.update_stage(
            job_id, Stage.searching, f"Retrieved {len(sources)} candidate source(s).", sources_found=len(sources)
        )

        await job_store.update_stage(job_id, Stage.analyzing, "Extracting evidence from sources...")
        evidence = await extract_evidence(sources, plan, llm, settings)

        await job_store.update_stage(job_id, Stage.verifying, "Checking conflicts and unsupported claims...")
        verification = await verify_evidence(evidence, sources, llm, settings)

        await job_store.update_stage(job_id, Stage.synthesizing, "Synthesizing final report...")
        report = await synthesize_report(
            request.question, sources, evidence, verification, len(plan.search_queries), llm, settings
        )

        duration = time.monotonic() - start
        usage = UsageStats(
            searches_performed=gather_stats.searches_performed,
            queries_attempted=gather_stats.queries_attempted,
            queries_with_results=gather_stats.queries_with_results,
            sources_retrieved=len(sources),
            sources_used=len(report.sources),
            llm_calls=llm.usage.calls,
            prompt_tokens=llm.usage.prompt_tokens,
            completion_tokens=llm.usage.completion_tokens,
            estimated_cost_usd=round(llm.usage.estimated_cost_usd, 6),
            duration_seconds=round(duration, 2),
            cache_hits=gather_stats.cache_hits,
        )

        job = ResearchJob(
            id=job_id,
            request=request,
            stage=Stage.done,
            report=report,
            usage=usage,
        )
        await storage.save_job(job)
        await job_store.complete(job_id, job)

    except Exception as exc:  # noqa: BLE001 - never let a bad run crash the server
        logger.exception("Research job %s failed", job_id)
        await job_store.fail(job_id, f"{type(exc).__name__}: {exc}")
