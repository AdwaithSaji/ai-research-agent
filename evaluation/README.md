# Evaluation

`run_eval.py` runs the full pipeline in-process (no HTTP server needed) over
`dataset.json`, a small set of representative research questions, and writes
metrics to `results/latest_results.json`.

## Running it

```bash
cd backend && python ../evaluation/run_eval.py
```

Default mode uses **real web search** (free DuckDuckGo scraping) but a
**mock LLM**, so retrieval/quality/diversity metrics reflect real retrieved
pages while the run costs nothing and needs no API key.

```bash
python evaluation/run_eval.py --live      # real search + real LLM (needs OPENAI_API_KEY)
SEARCH_PROVIDER=mock python evaluation/run_eval.py   # fully offline, deterministic (CI)
```

## Metrics

| Metric | What it measures | How |
|---|---|---|
| `retrieval_relevance` | Are retrieved sources actually on-topic? | Deterministic lexical overlap (Jaccard-style) between each source and its subquestion — the same signal the pipeline itself uses to filter sources, not a separate judge. |
| `citation_coverage` | Do generated findings cite a source? | Fraction of `key_findings` sentences containing a `[n]` marker. Only meaningful with a real LLM — the mock LLM emits fixed placeholder text. |
| `citation_validity` | Are cited markers real? | Fraction of `[n]` markers appearing in report text that resolve to an actual entry in `report.citations` — a direct hallucinated-citation check. |
| `grounding_rate` | Is each kept claim backed by a verbatim quote? | Fraction of surviving evidence items with a non-empty `quote` field. |
| `source_diversity` | Are sources coming from varied publishers? | unique domains / sources used. |
| `completeness` | Did every required report section get filled in? | Fraction of {executive_summary, methodology, analysis, uncertainty, conclusion} that are non-empty. |
| `latency_seconds`, `llm_calls`, tokens, `estimated_cost_usd` | Cost/performance | Directly from `UsageStats`. |

## Honest limitations

- 8 questions is enough to sanity-check behavior, not to draw statistically
  significant conclusions — this is a smoke-test-scale evaluation, not a
  benchmark paper.
- `retrieval_relevance` is the same lexical heuristic the pipeline itself uses
  for filtering, not an independent judge — it can't catch cases where the
  heuristic itself is wrong (e.g. paraphrased relevance with no shared
  vocabulary).
- Citation coverage/validity/grounding are only informative in `--live` mode;
  the default free/offline run mainly validates the retrieval side of the
  pipeline.
- DuckDuckGo's HTML endpoint occasionally rate-limits or changes markup;
  a run with zero sources for a question reflects that, not a pipeline bug —
  check `results/latest_results.json` for `insufficient_evidence: true`.
