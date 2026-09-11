"""Search tool abstraction.

Providers implement a single `search(query, max_results)` method returning
plain `SearchHit` records. Falling back gracefully (Tavily -> DuckDuckGo ->
Mock) means the agent degrades instead of failing outright when a provider
is unavailable or unconfigured.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""


class SearchError(RuntimeError):
    pass


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[SearchHit]:
        ...


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.tavily_api_key
        self._timeout = settings.fetch_timeout_seconds

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def search(self, query: str, max_results: int) -> list[SearchHit]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchHit(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", ""))
            for r in data.get("results", [])
            if r.get("url")
        ][:max_results]


class DuckDuckGoProvider(SearchProvider):
    """Scrapes the no-JS DuckDuckGo HTML endpoint. No API key required."""

    name = "duckduckgo"

    def __init__(self, settings: Settings) -> None:
        self._timeout = settings.fetch_timeout_seconds

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def search(self, query: str, max_results: int) -> list[SearchHit]:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": "Mozilla/5.0 (research-agent educational project)"},
            follow_redirects=True,
        ) as client:
            resp = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
            if resp.status_code >= 400:
                raise SearchError(f"DuckDuckGo returned HTTP {resp.status_code}")
            soup = BeautifulSoup(resp.text, "lxml")

        hits: list[SearchHit] = []
        for result in soup.select(".result")[: max_results * 2]:
            link = result.select_one(".result__a")
            if not link or not link.get("href"):
                continue
            snippet_el = result.select_one(".result__snippet")
            hits.append(
                SearchHit(
                    title=link.get_text(strip=True),
                    url=_clean_ddg_url(link["href"]),
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                )
            )
            if len(hits) >= max_results:
                break
        return hits


def _clean_ddg_url(href: str) -> str:
    """DDG html endpoint wraps result URLs in a redirect link; unwrap it."""
    if href.startswith("//duckduckgo.com/l/"):
        from urllib.parse import parse_qs, urlsplit

        qs = parse_qs(urlsplit(href).query)
        if "uddg" in qs:
            return qs["uddg"][0]
    return href


class MockSearchProvider(SearchProvider):
    """Offline, deterministic provider used in tests/mock mode."""

    name = "mock"

    async def search(self, query: str, max_results: int) -> list[SearchHit]:
        base = query.strip().replace(" ", "-").lower()[:40]
        return [
            SearchHit(
                title=f"Mock result {i+1} for '{query}'",
                url=f"https://example.org/{base}-{i+1}",
                snippet=f"This is a mock snippet discussing {query} (result {i+1}).",
            )
            for i in range(min(max_results, 3))
        ]


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except ValueError:
        return ""


def build_search_provider(settings: Settings) -> SearchProvider:
    mode = settings.search_provider
    if mode == "tavily" and settings.tavily_api_key:
        return TavilyProvider(settings)
    if mode == "duckduckgo":
        return DuckDuckGoProvider(settings)
    if mode == "mock":
        return MockSearchProvider()
    # auto
    if settings.tavily_api_key:
        return TavilyProvider(settings)
    return DuckDuckGoProvider(settings)
