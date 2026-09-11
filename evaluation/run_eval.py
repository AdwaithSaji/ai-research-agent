"""Local evaluation harness for the AI Research Agent.

Runs the full pipeline (Planner -> Researcher -> Evidence Analyst -> Verifier
-> Synthesizer) directly, in-process, over a small dataset of representative
research questions, and reports honest, reproducible metrics:

  - retrieval_relevance   avg. deterministic relevance score of sources used
  - citation_coverage     fraction of key findings that carry a [n] citation
  - citation_validity     fraction of citation markers that resolve to a real source
  - grounding_rate        fraction of kept evidence claims backed by a verbatim quote
  - source_diversity      unique domains / sources used
  - completeness          fraction of required report sections that are non-empty
  - latency_seconds, llm_calls, prompt/completion tokens, estimated cost

By default this uses REAL web search (free DuckDuckGo scraping, no API key
needed) but a MOCK LLM — so retrieval/quality/diversity metrics are measured
against real retrieved pages, at zero LLM cost. Pass --live to additionally
use a real LLM (requires OPENAI_API_KEY in the environment); citation
coverage/validity/grounding metrics are only meaningful in that mode, since
the mock LLM emits templated placeholder text instead of real synthesis.

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
    sources, searches_performed = await gather_sources(plan, search_provider, settings, search_cache, page_cache)
    evidence = await extract_evidence(sources, plan, llm, settings)
    verification = await verify_evidence(evidence, sources, llm, settings)
    report = await synthesize_report(
        item["question"], sources, evidence, verification, len(plan.search_queries), llm, settings
    )
    latency = time.monotonic() - start

    # --- metrics ---
    used_sources = report.sources
    valid_marker_nums = {c.marker for c in report.citations}

    kept_ids = set(verification.kept_evidence_ids)
    kept_evidence = [e for e in evidence if e.id in kept_ids]

    retrieval_relevance = mean([s.relevance_score for s in used_sources]) if used_sources else 0.0

    findings_with_citation = [f for f in report.key_findings if MARKER_RE.search(f)]
    citation_coverage = (
        len(findings_with_citation) / len(report.key_findings) if report.key_findings else None
    )

    all_markers_used = MARKER_RE.findall(
        report.executive_summary + " ".join(report.key_findings) + report.analysis
    )
    valid_marker_set = {m.strip("[]") for m in valid_marker_nums}
    citation_validity = (
        sum(1 for m in all_markers_used if m in valid_marker_set) / len(all_markers_used)
        if all_markers_used
        else None
    )

    grounding_rate = (
        sum(1 for e in kept_evidence if e.quote.strip()) / len(kept_evidence) if kept_evidence else None
    )

    unique_domains = {s.domain for s in used_sources}
    source_diversity = len(unique_domains) / len(used_sources) if used_sources else 0.0

    required_sections = [
        report.executive_summary,
        report.methodology,
        report.analysis,
        report.uncertainty,
        report.conclusion,
    ]
    completeness = sum(1 for s in required_sections if s.strip()) / len(required_sections)

    return {
        "id": item["id"],
        "question": item["question"],
        "insufficient_evidence": report.insufficient_evidence,
        "metrics": {
            "retrieval_relevance": round(retrieval_relevance, 3),
            "citation_coverage": citation_coverage,
            "citation_validity": citation_validity,
            "grounding_rate": grounding_rate,
            "source_diversity": round(source_diversity, 3),
            "completeness": round(completeness, 3),
            "latency_seconds": round(latency, 2),
        },
        "usage": {
            "searches_performed": searches_performed,
            "sources_retrieved": len(sources),
            "sources_used": len(used_sources),
            "llm_calls": llm.usage.calls,
            "prompt_tokens": llm.usage.prompt_tokens,
            "completion_tokens": llm.usage.completion_tokens,
            "estimated_cost_usd": round(llm.usage.estimated_cost_usd, 6),
        },
    }


def _aggregate(results: list[dict]) -> dict:
    def avg(key: str, sub: str = "metrics") -> float | None:
        values = [r[sub][key] for r in results if r[sub].get(key) is not None]
        return round(mean(values), 3) if values else None

    return {
        "n_questions": len(results),
        "avg_retrieval_relevance": avg("retrieval_relevance"),
        "avg_citation_coverage": avg("citation_coverage"),
        "avg_citation_validity": avg("citation_validity"),
        "avg_grounding_rate": avg("grounding_rate"),
        "avg_source_diversity": avg("source_diversity"),
        "avg_completeness": avg("completeness"),
        "avg_latency_seconds": avg("latency_seconds"),
        "total_llm_calls": sum(r["usage"]["llm_calls"] for r in results),
        "total_estimated_cost_usd": round(sum(r["usage"]["estimated_cost_usd"] for r in results), 6),
        "insufficient_evidence_rate": round(
            sum(1 for r in results if r["insufficient_evidence"]) / len(results), 3
        )
        if results
        else None,
    }


async def _main(live: bool) -> None:
    import os

    if not live:
        # Keep retrieval real (free) but force the LLM to mock mode so the
        # default run never costs money, regardless of what's in .env.
        os.environ["OPENAI_API_KEY"] = ""

    from app.config import Settings

    settings = Settings()
    dataset = _load_dataset()

    print(f"Running evaluation over {len(dataset)} questions "
          f"({'LIVE' if settings.openai_api_key else 'MOCK LLM'}, "
          f"search={settings.search_provider})...\n")

    results = []
    for item in dataset:
        print(f"  - {item['id']}: {item['question'][:70]}...")
        result = await _run_one(item, settings)
        results.append(result)

    summary = _aggregate(results)

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "latest_results.json"
    out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use real search/LLM providers from env config")
    args = parser.parse_args()
    asyncio.run(_main(args.live))
