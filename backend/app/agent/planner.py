"""Planner stage: decomposes the research question into subquestions + queries.

Produces a `ResearchPlan` whose subquestion -> search_queries relationship is
explicit in the data (`SubquestionPlan.search_queries`), not reconstructed
later via positional guessing — see app/models/schemas.py.
"""
from __future__ import annotations

from app.config import Settings
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import PLANNER_SYSTEM
from app.models.schemas import ResearchDepth, ResearchPlan, SubquestionPlan

_DEPTH_TO_SUBQ = {
    ResearchDepth.quick: 2,
    ResearchDepth.standard: 3,
    ResearchDepth.deep: 4,
}

# Cap on search queries generated per subquestion — bounds total search volume
# independently of how many queries a chatty LLM response tries to attach.
_MAX_QUERIES_PER_SUBQ = 2


async def plan_research(question: str, depth: ResearchDepth, llm: LLMClient, settings: Settings) -> ResearchPlan:
    max_subq = min(_DEPTH_TO_SUBQ.get(depth, 3), settings.max_subquestions)
    system = PLANNER_SYSTEM.format(max_subq=max_subq, max_queries_per_subq=_MAX_QUERIES_PER_SUBQ)
    user = f"Research question: {question}"

    items: list[SubquestionPlan] = []
    rationale = ""
    try:
        data = await llm.complete_json(system=system, user=user, max_tokens=500)
        for raw in data.get("subquestions", [])[:max_subq]:
            if not isinstance(raw, dict):
                continue
            subq = str(raw.get("subquestion", "")).strip()
            if not subq:
                continue
            queries = [str(q).strip() for q in raw.get("search_queries", []) if str(q).strip()]
            queries = _dedupe(queries)[:_MAX_QUERIES_PER_SUBQ]
            if not queries:
                queries = [subq]
            items.append(SubquestionPlan(subquestion=subq, search_queries=queries))
        rationale = str(data.get("rationale", ""))
    except LLMError:
        items = []

    if not items:
        # Deterministic fallback keeps the pipeline alive even if the LLM
        # response was unusable or malformed — never hard-fail the run.
        items = [SubquestionPlan(subquestion=question, search_queries=[question])]

    return ResearchPlan(items=items, rationale=rationale)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = v.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out
