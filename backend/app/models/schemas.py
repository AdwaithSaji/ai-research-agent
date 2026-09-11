"""Pydantic data contracts shared across the research pipeline stages.

Keeping these as explicit, serializable models (rather than passing loose
dicts between stages) is what makes the workflow "structured state between
stages" instead of an opaque agent loop.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, computed_field


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Request / configuration
# --------------------------------------------------------------------------

class ResearchDepth(str, Enum):
    quick = "quick"       # 2 subquestions, fewer sources
    standard = "standard"  # 3-4 subquestions
    deep = "deep"          # up to configured max


class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=8, max_length=500)
    depth: ResearchDepth = ResearchDepth.standard
    preferred_domains: list[str] = Field(default_factory=list, max_length=10)
    excluded_domains: list[str] = Field(default_factory=list, max_length=10)


# --------------------------------------------------------------------------
# Pipeline stages
# --------------------------------------------------------------------------

class Stage(str, Enum):
    queued = "queued"
    planning = "planning"
    searching = "searching"
    analyzing = "analyzing"
    verifying = "verifying"
    synthesizing = "synthesizing"
    done = "done"
    failed = "failed"


class SourceType(str, Enum):
    academic = "academic"
    government = "government"
    news = "news"
    organization = "organization"
    blog = "blog"
    documentation = "documentation"
    other = "other"


class SubquestionPlan(BaseModel):
    """A single subquestion with the search queries generated for it.

    Explicit subquestion -> queries[] structure (rather than two parallel
    flat lists matched up positionally) so the mapping from a search query
    back to its originating subquestion is a real, guaranteed relationship
    instead of an `index % len(subquestions)` guess.
    """

    subquestion: str
    search_queries: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    items: list[SubquestionPlan] = Field(default_factory=list)
    rationale: str = ""

    @property
    def subquestions(self) -> list[str]:
        return [i.subquestion for i in self.items]

    @property
    def search_queries(self) -> list[str]:
        """Flattened, order-preserving, case-insensitively deduplicated queries."""
        seen: set[str] = set()
        out: list[str] = []
        for item in self.items:
            for q in item.search_queries:
                key = q.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    out.append(q)
        return out

    def subquestion_for_query(self, query: str) -> str:
        """Exact lookup of the subquestion that generated `query` — no positional guessing."""
        for item in self.items:
            if query in item.search_queries:
                return item.subquestion
        return self.items[0].subquestion if self.items else query


class Source(BaseModel):
    id: str = Field(default_factory=_id)
    title: str
    url: str
    domain: str
    publisher: str = ""
    source_type: SourceType = SourceType.other
    retrieved_at: str = Field(default_factory=_now)
    snippet: str = ""
    content: str = ""  # extracted, trimmed main text
    fetch_ok: bool = False
    fetch_error: str | None = None
    quality_score: float = 0.0  # 0-1 heuristic
    relevance_score: float = 0.0  # 0-1, set by verifier
    query: str = ""  # search query that surfaced this source


class Evidence(BaseModel):
    id: str = Field(default_factory=_id)
    source_id: str
    subquestion: str
    claim: str
    quote: str = ""
    supports_answer: bool = True
    # Deterministically verified (not LLM-asserted): does `quote` actually
    # occur, after normalization, in the source's retrieved content? Empty
    # quotes are always unverified. See app/services/quote_verification.py.
    quote_verified: bool = False


class Conflict(BaseModel):
    topic: str
    description: str
    source_ids: list[str]


class VerificationResult(BaseModel):
    kept_evidence_ids: list[str]
    dropped_evidence_ids: list[str]
    conflicts: list[Conflict] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    notes: str = ""


class Citation(BaseModel):
    marker: str  # e.g. "[1]"
    source_id: str


class ReportSection(BaseModel):
    heading: str
    content: str


class ReportQualityStats(BaseModel):
    """Deterministic grounding statistics computed by backend code — never
    self-reported by the LLM — so a reader (or the evaluation harness) can
    check the report's own honesty claims instead of trusting prose."""

    total_evidence_extracted: int = 0
    evidence_kept_after_verification: int = 0
    quotes_attempted: int = 0
    quotes_verified: int = 0
    citation_markers_found: int = 0
    citation_markers_valid: int = 0
    citation_markers_invalid_removed: int = 0

    @computed_field  # type: ignore[misc]
    @property
    def quote_validity_rate(self) -> float | None:
        return round(self.quotes_verified / self.quotes_attempted, 3) if self.quotes_attempted else None

    @computed_field  # type: ignore[misc]
    @property
    def citation_validity_rate(self) -> float | None:
        return (
            round(self.citation_markers_valid / self.citation_markers_found, 3)
            if self.citation_markers_found
            else None
        )


class ResearchReport(BaseModel):
    question: str
    executive_summary: str
    methodology: str
    key_findings: list[str]
    evidence_summary: list[ReportSection] = Field(default_factory=list)
    conflicting_evidence: list[Conflict] = Field(default_factory=list)
    analysis: str
    uncertainty: str
    conclusion: str
    sources: list[Source]
    citations: list[Citation] = Field(default_factory=list)
    insufficient_evidence: bool = False
    quality_stats: ReportQualityStats = Field(default_factory=ReportQualityStats)


class UsageStats(BaseModel):
    searches_performed: int = 0  # network search calls actually made (cache misses)
    queries_attempted: int = 0  # total unique search queries in the plan
    queries_with_results: int = 0  # of those, how many returned >=1 hit
    sources_retrieved: int = 0
    sources_used: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    cache_hits: int = 0  # search + page-fetch results served from cache this run


class ProgressEvent(BaseModel):
    stage: Stage
    message: str
    sources_found: int = 0
    timestamp: str = Field(default_factory=_now)


class ResearchJob(BaseModel):
    id: str = Field(default_factory=_id)
    request: ResearchRequest
    stage: Stage = Stage.queued
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    events: list[ProgressEvent] = Field(default_factory=list)
    report: ResearchReport | None = None
    usage: UsageStats = Field(default_factory=UsageStats)
    error: str | None = None
