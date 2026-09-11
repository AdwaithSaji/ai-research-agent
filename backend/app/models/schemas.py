"""Pydantic data contracts shared across the research pipeline stages.

Keeping these as explicit, serializable models (rather than passing loose
dicts between stages) is what makes the workflow "structured state between
stages" instead of an opaque agent loop.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


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


class ResearchPlan(BaseModel):
    subquestions: list[str]
    search_queries: list[str]
    rationale: str = ""


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


class UsageStats(BaseModel):
    searches_performed: int = 0
    sources_retrieved: int = 0
    sources_used: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    cache_hits: int = 0


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
