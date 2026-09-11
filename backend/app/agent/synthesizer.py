"""Synthesizer stage: produces the final grounded ResearchReport.

Only evidence that survived the verifier is passed to the LLM. Citation
markers ([1], [2], ...) are assigned deterministically in code — the model
is told which marker maps to which piece of evidence and asked to reuse
them, so every citation in the final report corresponds to a real retrieved
source; nothing here lets the model invent a source.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import SYNTHESIZER_SYSTEM
from app.models.schemas import (
    Citation,
    Conflict,
    Evidence,
    ReportQualityStats,
    ReportSection,
    ResearchReport,
    Source,
    VerificationResult,
)
from app.services.citation_validator import sanitize_many

logger = logging.getLogger(__name__)

_MIN_EVIDENCE_FOR_CONFIDENT_REPORT = 2


def _build_methodology(n_queries: int, n_sources: int, n_evidence: int) -> str:
    return (
        f"The system decomposed the question, ran {n_queries} search queries, retrieved and "
        f"parsed {n_sources} candidate sources, deterministically filtered them for relevance and "
        f"quality, extracted {n_evidence} grounded evidence items via an LLM evidence-analyst pass, "
        f"and verified them for conflicts and unsupported claims before synthesis. All findings below "
        f"are grounded in the numbered sources; nothing is presented as fact without a citation."
    )


async def synthesize_report(
    question: str,
    sources: list[Source],
    evidence: list[Evidence],
    verification: VerificationResult,
    n_queries: int,
    llm: LLMClient,
    settings: Settings,
) -> ResearchReport:
    kept_ids = set(verification.kept_evidence_ids)
    kept_evidence = [e for e in evidence if e.id in kept_ids]

    # Deterministic citation marker assignment, in order of first appearance.
    marker_by_source: dict[str, str] = {}
    ordered_source_ids: list[str] = []
    for e in kept_evidence:
        if e.source_id not in marker_by_source:
            marker_by_source[e.source_id] = f"[{len(marker_by_source) + 1}]"
            ordered_source_ids.append(e.source_id)

    sources_by_id = {s.id: s for s in sources}
    used_sources = [sources_by_id[sid] for sid in ordered_source_ids if sid in sources_by_id]

    insufficient = len(kept_evidence) < _MIN_EVIDENCE_FOR_CONFIDENT_REPORT

    # Deterministic evidence_summary sections, grouped by subquestion — this
    # guarantees the "Evidence" section exactly reflects what was extracted,
    # without relying on the LLM to transcribe it faithfully.
    by_subq: dict[str, list[Evidence]] = {}
    for e in kept_evidence:
        by_subq.setdefault(e.subquestion, []).append(e)
    evidence_summary = [
        ReportSection(
            heading=subq,
            content="\n".join(
                f"- {e.claim} {marker_by_source.get(e.source_id, '')}" for e in items
            ),
        )
        for subq, items in by_subq.items()
    ]

    citations = [Citation(marker=m, source_id=sid) for sid, m in marker_by_source.items()]

    quotes_attempted = sum(1 for e in evidence if e.quote.strip())
    quotes_verified = sum(1 for e in evidence if e.quote_verified)

    if not kept_evidence:
        return ResearchReport(
            question=question,
            executive_summary=(
                "Insufficient verified evidence was found to answer this question with confidence. "
                "No sources passed relevance and quality filtering."
            ),
            methodology=_build_methodology(n_queries, len(sources), 0),
            key_findings=[],
            evidence_summary=[],
            conflicting_evidence=verification.conflicts,
            analysis="No analysis was produced because no evidence survived verification.",
            uncertainty="Evidence coverage is empty; treat this topic as unresearched by this system.",
            conclusion="Unable to draw a conclusion. Consider broadening the question or search sources.",
            sources=used_sources,
            citations=citations,
            insufficient_evidence=True,
            quality_stats=ReportQualityStats(
                total_evidence_extracted=len(evidence),
                evidence_kept_after_verification=0,
                quotes_attempted=quotes_attempted,
                quotes_verified=quotes_verified,
            ),
        )

    evidence_lines = "\n".join(
        f"{marker_by_source[e.source_id]} ({e.subquestion[:60]}): {e.claim}" for e in kept_evidence
    )
    conflict_lines = "\n".join(f"- {c.topic}: {c.description}" for c in verification.conflicts) or "None detected."
    user = (
        f"Research question: {question}\n\n"
        f"Verified evidence (cite using the bracketed markers shown):\n{evidence_lines}\n\n"
        f"Known conflicts:\n{conflict_lines}"
    )

    try:
        data = await llm.complete_json(system=SYNTHESIZER_SYSTEM, user=user, max_tokens=900)
    except LLMError as exc:
        logger.warning("Synthesizer LLM call failed: %s", exc)
        data = {}

    executive_summary = str(data.get("executive_summary", "")).strip() or (
        "A synthesis could not be generated; see the Evidence section for grounded findings."
    )
    key_findings = [str(k).strip() for k in data.get("key_findings", []) if str(k).strip()]
    analysis = str(data.get("analysis", "")).strip() or "No additional analysis generated."
    uncertainty = str(data.get("uncertainty", "")).strip() or (
        "Coverage may be incomplete; this system only reviewed a bounded set of web sources."
    )
    conclusion = str(data.get("conclusion", "")).strip() or "No conclusion generated."

    # Deterministic citation-marker guarantee: strip any [n] marker the LLM
    # wrote that doesn't correspond to a source actually cited above. The
    # model is never trusted to have gotten this right on its own.
    valid_markers = set(marker_by_source.values())
    fields_to_check = [executive_summary, analysis, conclusion, *key_findings]
    cleaned_fields, citation_stats = sanitize_many(fields_to_check, valid_markers)
    executive_summary, analysis, conclusion, *key_findings = cleaned_fields

    return ResearchReport(
        question=question,
        executive_summary=executive_summary,
        methodology=_build_methodology(n_queries, len(sources), len(kept_evidence)),
        key_findings=key_findings,
        evidence_summary=evidence_summary,
        conflicting_evidence=verification.conflicts,
        analysis=analysis,
        uncertainty=uncertainty,
        conclusion=conclusion,
        sources=used_sources,
        citations=citations,
        insufficient_evidence=insufficient,
        quality_stats=ReportQualityStats(
            total_evidence_extracted=len(evidence),
            evidence_kept_after_verification=len(kept_evidence),
            quotes_attempted=quotes_attempted,
            quotes_verified=quotes_verified,
            citation_markers_found=citation_stats.markers_found,
            citation_markers_valid=citation_stats.markers_valid,
            citation_markers_invalid_removed=citation_stats.markers_invalid_removed,
        ),
    )
