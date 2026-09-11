"""Source retrieval + lightweight content extraction.

Deliberately dependency-light (httpx + BeautifulSoup instead of a full
readability/boilerplate-removal stack) — good enough main-content extraction
for research snippets, without a heavy or fragile dependency chain.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.config import Settings

logger = logging.getLogger(__name__)

_STRIP_TAGS = ("script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg")
_ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass
class FetchResult:
    ok: bool
    title: str = ""
    text: str = ""
    error: str | None = None


async def fetch_and_extract(url: str, settings: Settings) -> FetchResult:
    try:
        async with httpx.AsyncClient(
            timeout=settings.fetch_timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0 (research-agent educational project)"},
            follow_redirects=True,
        ) as client:
            last_error: Exception | None = None
            for attempt in range(settings.fetch_max_retries + 1):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    break
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt == settings.fetch_max_retries:
                        return FetchResult(ok=False, error=f"{type(exc).__name__}: {exc}")
                    continue
            else:
                return FetchResult(ok=False, error=str(last_error))

        content_type = resp.headers.get("content-type", "")
        if not any(ct in content_type for ct in _ALLOWED_CONTENT_TYPES):
            return FetchResult(ok=False, error=f"Unsupported content-type: {content_type or 'unknown'}")

        return _extract(resp.text, settings.max_fetch_chars)

    except Exception as exc:  # noqa: BLE001 - never let one bad source crash the pipeline
        logger.warning("Unexpected fetch failure for %s: %s", url, exc)
        return FetchResult(ok=False, error=f"Unexpected error: {exc}")


def _extract(html: str, max_chars: int) -> FetchResult:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in main.find_all(["p", "li", "h1", "h2", "h3"])]
    text = "\n".join(p for p in paragraphs if len(p) > 40)

    if not text:
        text = main.get_text(" ", strip=True)

    text = text[:max_chars]
    if not text.strip():
        return FetchResult(ok=False, title=title, error="No extractable text content")

    return FetchResult(ok=True, title=title, text=text)
