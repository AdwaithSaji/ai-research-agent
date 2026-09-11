"""Evidence Analyst stage: extracts grounded claims from source content.

Cost control: (1) relevance-filters fetched sources deterministically before
spending any LLM call on them, (2) caps how many sources get an
evidence-extraction call, (3) trims each source's text to a small window
before sending it to the model instead of the whole page.
"""
from __future__ import annotations

import asyncio
import logging

from app.agent.researcher import subquestion_for_query
from app.config import Settings
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import EVIDENCE_ANALYST_SYSTEM
from app.models.schemas import Evidence, ResearchPlan, Source
from app.services.relevance import relevance_score

logger = logging.getLogger(__name__)


def select_sources_for_evidence(
    sources: list[Source], plan: ResearchPlan, settings: Settings
) -> list[Source]:
    """Deterministically rank fetched sources and keep only the most relevant ones."""
    usable = [s for s in sources if s.fetch_ok and s.content]

    for s in usable:
        subq = subquestion_for_query(plan, s.query)
        s.relevance_score = relevance_score(subq, s.title + " " + s.content)

    usable.sort(key=lambda s: (s.relevance_score, s.quality_score), reverse=True)
    return usable[: settings.max_sources_for_evidence]


async def extract_evidence(
    sources: list[Source], plan: ResearchPlan, llm: LLMClient, settings: Settings
) -> list[Evidence]:
    semaphore = asyncio.Semaphore(settings.request_concurrency)

    async def analyze_one(source: Source) -> list[Evidence]:
        subquestion = subquestion_for_query(plan, source.query)
        trimmed = source.content[: settings.max_evidence_chars_per_source]
        user = f"Subquestion: {subquestion}\n\nSource text:\n{trimmed}"
        async with semaphore:
            try:
                data = await llm.complete_json(system=EVIDENCE_ANALYST_SYSTEM, user=user, max_tokens=350)
            except LLMError as exc:
                logger.warning("Evidence extraction failed for %s: %s", source.url, exc)
                return []

        results: list[Evidence] = []
        for claim in data.get("claims", [])[:3]:
            text = str(claim.get("claim", "")).strip()
            if not text:
                continue
            results.append(
                Evidence(
                    source_id=source.id,
                    subquestion=subquestion,
                    claim=text,
                    quote=str(claim.get("quote", ""))[:300],
                    supports_answer=bool(claim.get("supports_answer", True)),
                )
            )
        return results

    selected = select_sources_for_evidence(sources, plan, settings)
    if not selected:
        return []

    results_per_source = await asyncio.gather(*(analyze_one(s) for s in selected))
    evidence: list[Evidence] = []
    for group in results_per_source:
        evidence.extend(group)
    return evidence
