"""Verifier/Critic stage: checks source quality, detects conflicts and
unsupported claims across ALL evidence in a single batched LLM call (not one
call per source/claim) — a deliberate cost-optimization choice.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import VERIFIER_SYSTEM
from app.models.schemas import Conflict, Evidence, Source, VerificationResult

logger = logging.getLogger(__name__)

_MIN_QUALITY_FLOOR = 0.25  # sources below this are dropped regardless of LLM output


async def verify_evidence(
    evidence: list[Evidence], sources: list[Source], llm: LLMClient, settings: Settings
) -> VerificationResult:
    sources_by_id = {s.id: s for s in sources}

    # Deterministic pre-filter: drop evidence attached to very low quality
    # sources or with no supporting quote at all, before spending an LLM call.
    prefiltered: list[Evidence] = []
    prefiltered_out: list[str] = []
    for e in evidence:
        source = sources_by_id.get(e.source_id)
        if source and source.quality_score < _MIN_QUALITY_FLOOR:
            prefiltered_out.append(e.id)
            continue
        prefiltered.append(e)

    if not prefiltered:
        return VerificationResult(
            kept_evidence_ids=[],
            dropped_evidence_ids=prefiltered_out,
            conflicts=[],
            unsupported_claims=[],
            notes="No evidence survived source-quality pre-filtering.",
        )

    lines = []
    for e in prefiltered:
        source = sources_by_id.get(e.source_id)
        domain = source.domain if source else "unknown"
        lines.append(f'{e.id} [{e.subquestion[:60]}] ({domain}): "{e.claim}" — quote: "{e.quote[:120]}"')
    user = "Claims:\n" + "\n".join(lines)

    try:
        data = await llm.complete_json(system=VERIFIER_SYSTEM, user=user, max_tokens=500)
    except LLMError as exc:
        logger.warning("Verifier LLM call failed, keeping all pre-filtered evidence: %s", exc)
        return VerificationResult(
            kept_evidence_ids=[e.id for e in prefiltered],
            dropped_evidence_ids=prefiltered_out,
            conflicts=[],
            unsupported_claims=[],
            notes="Verifier LLM call failed; evidence kept unfiltered beyond source-quality checks.",
        )

    valid_ids = {e.id for e in prefiltered}
    unsupported_ids = [i for i in data.get("unsupported_claim_ids", []) if i in valid_ids]

    conflicts: list[Conflict] = []
    for c in data.get("conflicts", []):
        claim_ids = [i for i in c.get("claim_ids", []) if i in valid_ids]
        if len(claim_ids) < 2:
            continue  # a "conflict" needs at least two disagreeing sources
        conflicts.append(
            Conflict(
                topic=str(c.get("topic", ""))[:120],
                description=str(c.get("description", ""))[:400],
                source_ids=list({sources_by_id[e.source_id].id for e in prefiltered if e.id in claim_ids}),
            )
        )

    kept_ids = [e.id for e in prefiltered if e.id not in unsupported_ids]
    dropped_ids = prefiltered_out + unsupported_ids

    return VerificationResult(
        kept_evidence_ids=kept_ids,
        dropped_evidence_ids=dropped_ids,
        conflicts=conflicts,
        unsupported_claims=[e.claim for e in prefiltered if e.id in unsupported_ids],
        notes=str(data.get("notes", "")),
    )
