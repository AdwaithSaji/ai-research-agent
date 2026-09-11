"""Deterministic verification that an LLM-extracted quote actually appears in
the source text it claims to come from.

The evidence-analyst LLM call is asked to copy quotes verbatim, but nothing
stops it from paraphrasing or lightly rewording — this is the backend check
that catches that, without trusting the model's own say-so. Verification is
substring matching after light normalization (whitespace, quote characters,
case), not exact byte equality — harmless formatting differences must not
produce false negatives — and it is NOT semantic similarity: a paraphrase
that changes the wording will correctly fail verification.
"""
from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_QUOTE_CHARS = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"', "‟": '"',
        "–": "-", "—": "-",
    }
)


def normalize_for_matching(text: str) -> str:
    """Lowercase, unify smart quotes/dashes, and collapse whitespace runs.

    Deliberately does NOT strip punctuation broadly — only the quote/dash
    characters that vary purely due to source formatting — so this stays a
    literal (substring) check, not a fuzzy/semantic one.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTE_CHARS)
    text = text.lower()
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def verify_quote(quote: str, source_content: str) -> bool:
    """Does `quote` occur verbatim (after normalization) in `source_content`?

    Empty/whitespace-only quotes are never considered verified — there is
    nothing to check, so it would be dishonest to mark them "verified".
    """
    quote = quote.strip()
    if not quote or not source_content:
        return False
    return normalize_for_matching(quote) in normalize_for_matching(source_content)
