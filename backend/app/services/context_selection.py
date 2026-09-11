"""Lightweight, deterministic selection of the most relevant slice of a
source's extracted text to send to the evidence-extraction LLM call.

Design decision: a naive `content[:max_chars]` prefix slice sends whatever
happened to be extracted first (often boilerplate intro text) and can miss
the paragraph that actually answers the subquestion if it appears later on
the page. An embedding-based re-ranker would fix that more precisely but adds
a model call/dependency for a problem a cheap heuristic already solves well
enough at this scale (a handful of paragraphs per source): split the
extracted text into paragraphs (fetch.py already emits one per line), score
each by the same lexical word-overlap heuristic used elsewhere in the
pipeline (`app.services.relevance`), and keep the highest-scoring paragraphs
— up to the character budget — in their original document order, so the
evidence-extraction prompt still reads as coherent prose.
"""
from __future__ import annotations

from app.services.relevance import relevance_score


def split_into_paragraphs(content: str) -> list[str]:
    """Recovers paragraph-like units from extracted page text.

    `app.tools.fetch` joins extracted `<p>/<li>/<h1-3>` text with newlines,
    so splitting on newlines recovers those units directly; this also
    degrades gracefully for arbitrary text with blank-line-separated
    paragraphs (blank lines are simply filtered out).
    """
    return [p.strip() for p in content.split("\n") if p.strip()]


def select_relevant_context(content: str, query_text: str, max_chars: int) -> str:
    """Return up to `max_chars` of `content`, prioritizing paragraphs most
    relevant to `query_text`, restored to original document order.

    Falls back to a plain prefix slice when the content has no paragraph
    structure at all (e.g. a single unbroken blob of text).
    """
    if len(content) <= max_chars:
        return content

    paragraphs = split_into_paragraphs(content)
    if len(paragraphs) <= 1:
        return content[:max_chars]

    scored = [(relevance_score(query_text, p), idx, p) for idx, p in enumerate(paragraphs)]
    # Highest relevance first; stable original order as tiebreak.
    scored.sort(key=lambda t: (-t[0], t[1]))

    selected_indices: list[int] = []
    total = 0
    for _, idx, p in scored:
        if selected_indices and total + len(p) + 1 > max_chars:
            continue
        selected_indices.append(idx)
        total += len(p) + 1
        if total >= max_chars:
            break

    selected_indices.sort()  # restore original document order
    result = "\n".join(paragraphs[i] for i in selected_indices)
    return result[:max_chars]
