"""Local evaluation harness for the AI Research Agent.

Runs the full pipeline (Planner -> Researcher -> Evidence Analyst -> Verifier
-> Synthesizer) directly, in-process, over a dataset of representative
research questions spanning several categories, and reports honest,
reproducible metrics.

Two distinct modes, always labeled explicitly in the output as `llm_mode`:

  - "mock" (default): REAL web search (free DuckDuckGo scraping, no API key
    needed) but a MOCK LLM. Retrieval/quality/diversity metrics are measured
    against real retrieved pages, at zero LLM cost. Citation/quote/coverage
    metrics are NOT meaningful here — the mock LLM emits fixed placeholder
    text and empty quotes by design — and are reported as such.
  - "real" (--live, requires OPENAI_API_KEY): real search + real LLM. This is
    the only mode where citation/quote/grounding metrics reflect actual model
    behavior. Costs money.

Metrics computed per question (see ReportQualityStats on the report itself
for the deterministic grounding numbers — this script does not re-derive
citation/quote validity independently, it trusts the same backend-computed
stats the API returns, which is the point: one source of truth):

  - retrieval_relevance    avg. deterministic relevance score of sources used
  - source_diversity       unique domains / sources used
  - completeness           fraction of required report sections that are non-empty
  - citation_coverage      fraction of key findings carrying a [n] marker
  - citation_validity_rate valid citation markers / all markers found (from report.quality_stats)
  - quote_validity_rate    verified quotes / attempted quotes (from report.quality_stats)
  - evidence_retention     evidence kept after verification / evidence extracted
  - search_success_rate    queries that returned >=1 hit / queries attempted
  - latency_seconds, llm_calls, prompt/completion tokens, estimated cost

Usage:
    python evaluation/run_eval.py            # real search, mock LLM (free)
    python evaluation/run_eval.py --live      # real search + real LLM (costs money)
    SEARCH_PROVIDER=mock python evaluation/run_eval.py   # fully offline (CI)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

MARKER_RE = re.compile(r"\[(\d+)\]")


def _load_dataset() -> list[dict]:
    path = Path(__file__).resolve().parent / "dataset.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def _run_one(item: dict, settings) -> dict:
    from app.agent.evidence import extract_evidence
    from app.agent.planner import plan_research
    from app.agent.researcher import gather_sources
    from app.agent.synthesizer import synthesize_report
    from app.agent.verifier import verify_evidence
    from app.llm.client import build_llm_client
    from app.models.schemas import ResearchDepth
    from app.services.cache import TTLCache
    from app.tools.search import build_search_provider

    llm = build_llm_client(settings)
    search_provider = build_search_provider(settings)
    search_cache: TTLCache = TTLCache()
    page_cache: TTLCache = TTLCache()

    start = time.monotonic()
    plan = await plan_research(item["question"], ResearchDepth(item.get("depth", "standard")), llm, settings)
    sources, gather_stats = await gather_sources(plan, search_provider, settings, search_cache, page_cache)
    evidence = await extract_evidence(sources, plan, llm, settings)
    verification = await verify_evidence(evidence, sources, llm, settings)
    report = await synthesize_report(
        item["question"], sources, evidence, verification, len(plan.search_queries), llm, settings
    )
    latency = time.monotonic() - start

    # --- metrics not already computed deterministically on the report itself ---
    used_sources = report.sources
    retrieval_relevance = mean([s.relevance_score for s in used_sources]) if used_sources else 0.0

    findings_with_citation = [f for f in report.key_findings if MARKER_RE.search(f)]
    citation_coverage = (
        len(findings_with_citation) / len(report.key_findings) if report.key_findings else None
    )

    unique_domains = {s.domain for s in used_sources}
    source_diversity = len(unique_domains) / len(used_sources) if used_sources else 0.0

    required_sections = [
        report.executive_summary, report.methodology, report.analysis, report.uncertainty, report.conclusion,
    ]
    completeness = sum(1 for s in required_sections if s.strip()) / len(required_sections)

    qs = report.quality_stats
    evidence_retention = (
        qs.evidence_kept_after_verification / qs.total_evidence_extracted if qs.total_evidence_extracted else None
    )
    search_success_rate = (
        gather_stats.queries_with_results / gather_stats.queries_attempted if gather_stats.queries_attempted else None
    )

    return {
        "id": item["id"],
        "category": item.get("category", "uncategorized"),
        "question": item["question"],
        "insufficient_evidence": report.insufficient_evidence,
        "error": None,
        "metrics": {
            "retrieval_relevance": round(retrieval_relevance, 3),
            "source_diversity": round(source_diversity, 3),
            "completeness": round(completeness, 3),
            "citation_coverage": citation_coverage,
            "citation_validity_rate": qs.citation_validity_rate,
            "quote_validity_rate": qs.quote_validity_rate,
            "evidence_retention": round(evidence_retention, 3) if evidence_retention is not None else None,
            "search_success_rate": round(search_success_rate, 3) if search_success_rate is not None else None,
            "latency_seconds": round(latency, 2),
        },
        "usage": {
            "searches_performed": gather_stats.searches_performed,
            "cache_hits": gather_stats.cache_hits,
            "sources_retrieved": len(sources),
            "sources_used": len(used_sources),
            "llm_calls": llm.usage.calls,
            "prompt_tokens": llm.usage.prompt_tokens,
            "completion_tokens": llm.usage.completion_tokens,
            "estimated_cost_usd": round(llm.usage.estimated_cost_usd, 6),
        },
    }


def _aggregate(results: list[dict]) -> dict:
    ok_results = [r for r in results if r.get("error") is None]

    def avg(key: str, sub: str = "metrics") -> float | None:
        values = [r[sub][key] for r in ok_results if r[sub].get(key) is not None]
        return round(mean(values), 3) if values else None

    return {
        "n_questions": len(results),
        "n_failed": sum(1 for r in results if r.get("error") is not None),
        "avg_retrieval_relevance": avg("retrieval_relevance"),
        "avg_source_diversity": avg("source_diversity"),
        "avg_completeness": avg("completeness"),
        "avg_citation_coverage": avg("citation_coverage"),
        "avg_citation_validity_rate": avg("citation_validity_rate"),
        "avg_quote_validity_rate": avg("quote_validity_rate"),
        "avg_evidence_retention": avg("evidence_retention"),
        "avg_search_success_rate": avg("search_success_rate"),
        "avg_latency_seconds": avg("latency_seconds"),
        "total_llm_calls": sum(r["usage"]["llm_calls"] for r in ok_results),
        "total_cache_hits": sum(r["usage"]["cache_hits"] for r in ok_results),
        "total_estimated_cost_usd": round(sum(r["usage"]["estimated_cost_usd"] for r in ok_results), 6),
        "insufficient_evidence_rate": (
            round(sum(1 for r in ok_results if r["insufficient_evidence"]) / len(ok_results), 3)
            if ok_results
            else None
        ),
    }


async def _main(live: bool) -> None:
    import os

    if not live:
        # Keep retrieval real (free) but force the LLM to mock mode so the
        # default run never costs money, regardless of what's in .env.
        os.environ["OPENAI_API_KEY"] = ""

    from app.config import Settings

    settings = Settings()
    llm_mode = "real" if settings.openai_api_key else "mock"
    dataset = _load_dataset()

    print(f"Running evaluation over {len(dataset)} questions "
          f"(llm_mode={llm_mode}, search={settings.search_provider})...\n")
    if llm_mode == "mock":
        print("NOTE: citation/quote/coverage metrics are not meaningful in mock mode "
              "(the mock LLM emits fixed placeholder text). Use --live for those.\n")

    results = []
    for item in dataset:
        print(f"  - [{item.get('category', '?')}] {item['id']}: {item['question'][:65]}...")
        try:
            result = await _run_one(item, settings)
        except Exception as exc:  # noqa: BLE001 - one bad question must not abort the whole eval run
            result = {
                "id": item["id"],
                "category": item.get("category", "uncategorized"),
                "question": item["question"],
                "insufficient_evidence": None,
                "error": f"{type(exc).__name__}: {exc}",
                "metrics": {},
                "usage": {},
            }
        results.append(result)

    summary = _aggregate(results)

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "latest_results.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "llm_mode": llm_mode,
        "search_provider": settings.search_provider,
        "dataset_size": len(dataset),
        "summary": summary,
        "results": results,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    print(f"llm_mode: {llm_mode}")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use real search/LLM providers from env config")
    args = parser.parse_args()
    asyncio.run(_main(args.live))
