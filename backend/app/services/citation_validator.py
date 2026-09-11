"""Deterministic citation-marker validation.

Citation markers ([1], [2], ...) are assigned in code by the synthesizer from
sources that were actually retrieved (see app/agent/synthesizer.py) — the LLM
is only ever told which markers exist and asked to reuse them. But the model
still free-generates the surrounding prose (executive summary, key findings,
analysis), and nothing stops it from typing a marker number that was never
assigned (e.g. "[7]" when only 5 sources were cited). This module is the
backend-code guarantee that no such marker survives into the final report —
no extra LLM call, just a regex scan and a set-membership check.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass
class CitationCheckResult:
    text: str
    markers_found: int
    markers_valid: int
    markers_invalid_removed: int


def sanitize_citations(text: str, valid_markers: set[str]) -> CitationCheckResult:
    """Strip any `[n]` marker not present in `valid_markers` from `text`.

    `valid_markers` holds marker strings including brackets, e.g. {"[1]", "[2]"}.
    Invalid markers are removed (not replaced with a fabricated stand-in) and
    the surrounding whitespace is collapsed so removal doesn't leave doubled
    spaces or dangling punctuation gaps.
    """
    if not text:
        return CitationCheckResult(text=text, markers_found=0, markers_valid=0, markers_invalid_removed=0)

    found = _MARKER_RE.findall(text)
    total_found = len(found)
    valid_numbers = {m.strip("[]") for m in valid_markers}
    valid_count = sum(1 for n in found if n in valid_numbers)
    invalid_count = total_found - valid_count

    if invalid_count == 0:
        return CitationCheckResult(text=text, markers_found=total_found, markers_valid=valid_count, markers_invalid_removed=0)

    def _replace(match: re.Match) -> str:
        return match.group(0) if match.group(1) in valid_numbers else ""

    cleaned = _MARKER_RE.sub(_replace, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)  # tidy up "word ." left by a removed marker
    cleaned = cleaned.strip()

    return CitationCheckResult(
        text=cleaned, markers_found=total_found, markers_valid=valid_count, markers_invalid_removed=invalid_count
    )


def sanitize_many(texts: list[str], valid_markers: set[str]) -> tuple[list[str], CitationCheckResult]:
    """Sanitize several text fields at once and return the combined stats."""
    cleaned_texts = []
    total_found = total_valid = total_invalid = 0
    for text in texts:
        result = sanitize_citations(text, valid_markers)
        cleaned_texts.append(result.text)
        total_found += result.markers_found
        total_valid += result.markers_valid
        total_invalid += result.markers_invalid_removed
    return cleaned_texts, CitationCheckResult(
        text="", markers_found=total_found, markers_valid=total_valid, markers_invalid_removed=total_invalid
    )
