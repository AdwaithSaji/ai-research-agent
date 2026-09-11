"""Planner stage: decomposes the research question into subquestions + queries."""
from __future__ import annotations

from app.config import Settings
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import PLANNER_SYSTEM
from app.models.schemas import ResearchDepth, ResearchPlan

_DEPTH_TO_SUBQ = {
    ResearchDepth.quick: 2,
    ResearchDepth.standard: 3,
    ResearchDepth.deep: 4,
}


async def plan_research(question: str, depth: ResearchDepth, llm: LLMClient, settings: Settings) -> ResearchPlan:
    max_subq = min(_DEPTH_TO_SUBQ.get(depth, 3), settings.max_subquestions)
    system = PLANNER_SYSTEM.format(max_subq=max_subq)
    user = f"Research question: {question}"

    try:
        data = await llm.complete_json(system=system, user=user, max_tokens=400)
        subquestions = [str(s).strip() for s in data.get("subquestions", []) if str(s).strip()][:max_subq]
        queries = [str(q).strip() for q in data.get("search_queries", []) if str(q).strip()]
        rationale = str(data.get("rationale", ""))
    except LLMError:
        subquestions, queries, rationale = [], [], ""

    if not subquestions:
        # Deterministic fallback keeps the pipeline alive even if the LLM
        # response was unusable — never hard-fail the whole run over planning.
        subquestions = [question]
    if not queries:
        queries = [question]

    # Deduplicate queries case-insensitively (cost control: never search the
    # same string twice) while preserving order and 1:1-ish alignment length.
    seen: set[str] = set()
    deduped_queries: list[str] = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped_queries.append(q)

    return ResearchPlan(subquestions=subquestions, search_queries=deduped_queries, rationale=rationale)
