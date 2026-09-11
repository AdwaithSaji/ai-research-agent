# Evaluation

`run_eval.py` runs the full pipeline in-process (no HTTP server needed) over
`dataset.json` — 22 representative research questions across 6 categories
(AI/ML, generative AI, software engineering, cybersecurity, science/tech,
general research) — and writes results to `results/latest_results.json`.

## Running it

```bash
cd backend && python ../evaluation/run_eval.py
```

Default mode uses **real web search** (free DuckDuckGo scraping) but a
**mock LLM**, so retrieval/quality/diversity metrics reflect real retrieved
pages while the run costs nothing and needs no API key.

```bash
python evaluation/run_eval.py --live      # real search + real LLM (needs OPENAI_API_KEY, costs money)
SEARCH_PROVIDER=mock python evaluation/run_eval.py   # fully offline, deterministic (CI)
```

The output JSON always labels which mode produced it via a top-level
`llm_mode: "mock" | "real"` field, plus `timestamp`, `search_provider`, and
`dataset_size` — never presented ambiguously.

## Metrics

| Metric | What it measures | How | Meaningful in mock mode? |
|---|---|---|---|
| `retrieval_relevance` | Are retrieved sources actually on-topic? | Deterministic lexical overlap (Jaccard-style) between each source and its subquestion — the same signal the pipeline itself uses to filter sources. | Yes |
| `source_diversity` | Are sources coming from varied publishers? | unique domains / sources used. | Yes |
| `completeness` | Did every required report section get filled in? | Fraction of {executive_summary, methodology, analysis, uncertainty, conclusion} that are non-empty. | Yes |
| `search_success_rate` | Are search queries actually returning results? | queries that returned ≥1 hit / queries attempted. | Yes |
| `evidence_retention` | How much extracted evidence survives verification? | `evidence_kept_after_verification / total_evidence_extracted`, read directly from `report.quality_stats`. | Yes |
| `citation_coverage` | Do generated findings cite a source? | Fraction of `key_findings` sentences containing a `[n]` marker. | **No** — the mock LLM emits fixed placeholder text with no markers. |
| `citation_validity_rate` | Are cited markers real? | `citation_markers_valid / citation_markers_found`, read directly from `report.quality_stats` (computed by `app/services/citation_validator.py`, not re-derived here). | **No** — undefined (no markers exist to check) in mock mode. |
| `quote_validity_rate` | Is each extracted quote actually in the source? | `quotes_verified / quotes_attempted`, from `report.quality_stats` (`app/services/quote_verification.py`). | **No** — the mock LLM always returns empty quotes. |
| `latency_seconds`, `llm_calls`, `cache_hits`, tokens, `estimated_cost_usd` | Cost/performance | Directly from `UsageStats` / `GatherStats`. | Yes |

Note the deterministic grounding stats (citation validity, quote validity,
evidence retention) are **read from the report itself**
(`report.quality_stats`), not recomputed independently by this script — the
whole point of computing them once, in backend code, is that there's a
single source of truth to trust.

## Honest limitations

- 22 questions is enough to sanity-check behavior broadly across domains,
  not to draw statistically significant conclusions — this is a
  smoke-test-scale evaluation, not a benchmark paper.
- `retrieval_relevance` and the paragraph-selection logic it feeds are the
  same lexical heuristic the pipeline itself uses, not an independent judge
  — this script can't catch cases where the heuristic itself is wrong (e.g.
  paraphrased relevance with no shared vocabulary).
- Citation coverage/validity and quote validity are **only** informative in
  `--live` mode; the default free/offline run mainly validates the
  retrieval side of the pipeline. Never interpret mock-mode `0.0`/`null`
  values for those metrics as a statement about real model quality.
- DuckDuckGo's HTML endpoint occasionally rate-limits or changes markup;
  a run with zero sources for a question reflects that, not a pipeline bug —
  check `results/latest_results.json` for `insufficient_evidence: true` or
  a per-question `error` field (a failed question is recorded, not allowed
  to crash the whole evaluation run).
- Results are not committed to the repository (regenerate them locally) —
  they're a reproducible artifact of a live web search, not a fixed dataset,
  so a committed copy would go stale immediately.
