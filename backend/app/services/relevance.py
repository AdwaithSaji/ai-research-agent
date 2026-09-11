"""Deterministic (non-LLM) relevance scoring.

Used to rank and filter sources *before* the expensive evidence-extraction
LLM call — a core token/cost-optimization lever: don't pay for an LLM call on
a source that a cheap lexical check already shows is off-topic.
"""
from __future__ import annotations

import re

_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are",
    "what", "how", "why", "does", "do", "with", "about", "current", "approaches",
    "that", "this", "be", "as", "it", "by", "at", "from", "into",
}
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


def relevance_score(query_text: str, source_text: str) -> float:
    """Jaccard-style overlap between query/subquestion tokens and source tokens.

    Returns 0.0-1.0. Cheap, explainable, and stable — no LLM call required.
    """
    query_tokens = _tokens(query_text)
    if not query_tokens:
        return 0.0
    source_tokens = _tokens(source_text[:3000])
    if not source_tokens:
        return 0.0
    overlap = query_tokens & source_tokens
    return round(len(overlap) / len(query_tokens), 3)
