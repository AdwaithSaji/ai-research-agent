"""Deterministic source-quality heuristics.

This is intentionally simple, explainable, and rule-based rather than another
LLM call — it's cheap, fast, reproducible, and doesn't need to be "right" in
an absolute sense, only useful as a relative signal for ranking and for
flagging low-confidence sources to the reader. It is a heuristic, not a claim
of objective truth about source credibility.
"""
from __future__ import annotations

import re

from app.models.schemas import SourceType

_ACADEMIC_DOMAINS = (".edu", "arxiv.org", "acm.org", "ieee.org", "nature.com", "science.org",
                      "springer.com", "sciencedirect.com", "ncbi.nlm.nih.gov", "jstor.org")
_GOV_DOMAINS = (".gov", ".mil", "who.int", "un.org", "europa.eu")
_ORG_DOMAINS = (".org",)
_NEWS_DOMAINS = ("nytimes.com", "bbc.co", "reuters.com", "apnews.com", "theguardian.com",
                 "wsj.com", "bloomberg.com", "npr.org", "washingtonpost.com", "economist.com")
_DOC_DOMAINS = ("docs.", "developer.", "readthedocs.io", "github.io")
_LOW_TRUST_HINTS = ("blogspot.", "medium.com", "wordpress.com", "substack.com")

_DATE_RE = re.compile(r"\b(20[0-2][0-9])\b")


def classify_source_type(domain: str) -> SourceType:
    d = domain.lower()
    if any(a in d for a in _ACADEMIC_DOMAINS):
        return SourceType.academic
    if any(g in d for g in _GOV_DOMAINS):
        return SourceType.government
    if any(n in d for n in _NEWS_DOMAINS):
        return SourceType.news
    if any(doc in d for doc in _DOC_DOMAINS):
        return SourceType.documentation
    if any(b in d for b in _LOW_TRUST_HINTS):
        return SourceType.blog
    if any(o in d for o in _ORG_DOMAINS):
        return SourceType.organization
    return SourceType.other


_TYPE_BASE_SCORE = {
    SourceType.academic: 0.95,
    SourceType.government: 0.9,
    SourceType.organization: 0.7,
    SourceType.news: 0.65,
    SourceType.documentation: 0.6,
    SourceType.blog: 0.35,
    SourceType.other: 0.5,
}


def score_source_quality(domain: str, text: str, current_year: int = 2026) -> float:
    """Return a 0-1 heuristic quality score.

    Factors: source-type prior (primary/official/academic sources score
    higher than blogs), and a mild recency signal from any 4-digit year
    mentioned in the text (rewards content referencing recent years).
    """
    source_type = classify_source_type(domain)
    score = _TYPE_BASE_SCORE[source_type]

    years = [int(y) for y in _DATE_RE.findall(text[:2000])]
    if years:
        most_recent = max(years)
        age = max(0, current_year - most_recent)
        recency_factor = max(0.0, 1 - age / 10)  # linear decay over ~10 years
        score = 0.8 * score + 0.2 * recency_factor

    return round(min(1.0, max(0.0, score)), 3)
