# PROJECT_CONTEXT — Mismatch

## Current completed step
- Step 10 complete (LangGraph agent + strict schema output)
- `/chat` endpoint wired to LangGraph StateGraph agent

## Current doc setup
- Canonical spec: `AGENTS.md`
- Live handoff: `PROJECT_CONTEXT.md`

## What exists in the repo
- `services/agent/app/main.py` — FastAPI with /health and /chat endpoints
- `services/agent/app/schemas.py` — ChatRequest and ChatResponse models
- `services/agent/app/settings.py` — all env vars including data paths, API base URLs, Cohere
- `services/agent/app/clients/openai_embeddings.py` — EmbeddingClient wrapping text-embedding-3-small (1536 dims)
- `services/agent/app/retrieval/service.py` — RetrievedDocument dataclass with to_citation()
- `services/agent/app/retrieval/qdrant_store.py` — QdrantRetrievalService (ensure_collection, query_points with filters, upsert_jsonl with batching)
- `services/agent/app/pipeline/build_docs.py` — CSV parsing, rest/b2b computation, team/season summaries, validation logs
- `services/agent/app/utils/team_names.py` — normalize_team_name() + slugify_team_name() + Kalshi abbreviation maps
- `services/agent/app/eval/__init__.py` — eval package
- `services/agent/app/eval/rag_chain.py` — baseline + reranked RAG chains for RAGAS eval (RAGResult with token usage tracking)
- `services/agent/app/eval/helpers.py` — shared eval utilities (metrics, cost estimation, LangSmith upload)
- `services/agent/app/retrieval/reranker.py` — CohereRerank + ContextualCompressionRetriever (retrieve 10, rerank to 5)
- `services/agent/app/tools/odds_math.py` — american_to_implied, devig_multiplicative, compute_edge
- `services/agent/app/tools/models.py` — GameOdds, KalshiMarket, MatchupEdge, TavilyResult dataclasses
- `services/agent/app/tools/odds_api.py` — OddsAPIClient (fetch NHL odds, average across bookmakers, de-vig)
- `services/agent/app/tools/kalshi.py` — KalshiClient (fetch KXNHLGAME markets, parse tickers, resolve teams)
- `services/agent/app/tools/tavily.py` — TavilyClient (web search via httpx)
- `services/agent/app/tools/match.py` — build_matchup_edges() keyed by (team, date) — matches Odds API to Kalshi, computes edges, BET/PASS
- `services/agent/scripts/build_docs.py` — CLI to run pipeline -> docs.jsonl
- `services/agent/scripts/upsert_docs.py` — CLI to upsert docs.jsonl -> Qdrant
- `services/agent/scripts/generate_testset.py` — RAGAS TestsetGenerator with doc sampling, static personas, and retry logic (uploads to LangSmith)
- `services/agent/scripts/eval_baseline.py` — RAGAS baseline eval (5 metrics + latency/cost tracking, per-query upload to LangSmith)
- `services/agent/scripts/eval_advanced.py` — RAGAS advanced eval with Cohere rerank + baseline comparison table
- `services/agent/data/processed/docs.jsonl` — 2,251 docs (288 per-team + ~1,467 h2h_season + ~496 h2h_recent)
- `services/agent/data/eval/testset.json` — 51 synthetic eval examples (RAGAS TestsetGenerator, ~50 target)
- `services/agent/data/eval/baseline_results.json` — baseline RAGAS scores + latency/cost performance
- `services/agent/data/eval/advanced_results.json` — advanced (Cohere rerank) RAGAS scores + latency/cost performance
- `services/agent/pyproject.toml` — all deps including ragas, langchain-openai, langchain-cohere
- `web/` — Next.js chat UI with /api/chat proxy
- `data/raw/` — 3 NHL season CSVs

## Step 7 baseline RAGAS results
```json
{
  "revision_id": "baseline",
  "retrieval": "dense_cosine_qdrant",
  "retrieval_limit": 6,
  "num_examples": 51,
  "metrics": {
    "faithfulness": 0.828,
    "context_recall": 0.713,
    "context_entity_recall": 0.356,
    "answer_relevancy": 0.642,
    "factual_correctness": 0.445
  },
  "performance": {
    "avg_latency_ms": 2571,
    "p95_latency_ms": 5665,
    "total_cost_usd": 0.0087
  }
}
```
- Golden dataset: 51 synthetic examples via RAGAS TestsetGenerator (SingleHop 50%, MultiHopAbstract 25%, MultiHopSpecific 25%)
- Synthetic generation uses stratified doc sampling (100 of 2,251 docs) and static personas
- Doc corpus: 2,251 docs (288 per-team summaries + 1,467 h2h_season + 496 h2h_recent)
- Per-query metrics, latency, and cost uploaded to LangSmith (`mismatch-eval-baseline` dataset)

## Step 8 advanced RAGAS results (Cohere rerank)
```json
{
  "revision_id": "cohere_rerank",
  "retrieval": "dense_cosine_qdrant+cohere_rerank_v3.5",
  "retrieval_limit": 10,
  "rerank_top_n": 5,
  "num_examples": 51,
  "metrics": {
    "faithfulness": 0.911,
    "context_recall": 0.758,
    "context_entity_recall": 0.360,
    "answer_relevancy": 0.672,
    "factual_correctness": 0.399
  },
  "performance": {
    "avg_latency_ms": 6393,
    "p95_latency_ms": 29615,
    "total_cost_usd": 0.0078
  }
}
```

### Baseline vs Advanced comparison
| Metric | Baseline | Advanced | Delta |
|---|---|---|---|
| faithfulness | 0.828 | 0.911 | **+0.084** |
| context_recall | 0.713 | 0.758 | **+0.045** |
| context_entity_recall | 0.356 | 0.360 | +0.004 |
| answer_relevancy | 0.642 | 0.672 | **+0.030** |
| factual_correctness | 0.445 | 0.399 | -0.047 |

- Reranking improved faithfulness (+8.4%), context_recall (+4.5%), and answer_relevancy (+3.0%)
- context_entity_recall was flat; factual_correctness dipped slightly (-4.7%)
- Latency increased due to extra Cohere API call + trial key rate limiting
- Per-query results uploaded to LangSmith (`mismatch-eval-advanced` dataset)

## Step 9 design notes

### 7-day window scoping
AGENTS.md §2 specifies "today through 7 days out". This is enforced architecturally, not via explicit date filters:
- **Odds API** only returns games with active betting lines (~1-3 days out). No parameter exists to request a wider window.
- **Kalshi** `status=open` markets are listed ~2-4 days ahead at most.
- **match.py** keys on `(team, date)` — only games present in *both* APIs are matched, so the intersection is inherently short-window.
An explicit `timedelta(days=7)` filter would be dead code that never triggers.

### Matchup mapping
`match.py` uses `(normalized_team_name, game_date)` as the composite key to prevent overwrites when a team has markets on multiple dates.

## Dependency readiness
- OpenAI: ready
- Qdrant Cloud: ready (2,251 docs upserted to mismatch_docs collection)
- LangSmith: ready (golden dataset uploaded)
- Odds API: ready (500 req/mo free tier, h2h market, American odds)
- Kalshi: ready (api.elections.kalshi.com, KXNHLGAME series, no auth for reads)
- Tavily: ready (search API)
- Cohere: ready (rerank-v3.5, trial key with 10 req/min rate limit)

## Step 10 implementation notes

### LangGraph agent architecture
- **Graph shape:** START -> interpret_intent -> retrieve -> fetch_odds_and_kalshi -> compute_edges -> [gate] -> tavily_search? -> generate_response -> END
- **LLM calls:** 2 per request (intent classification + rationale/freeform generation) via gpt-4o-mini
- **Tavily gating:** conditional edge — searches only if any edge has BET recommendation OR intent is "explanation" OR query contains explanation keywords
- **Strict §8 formatting:** game blocks (Recommendation, Game, Kalshi Probability, Fair Probability, Edge, Rationale) are built deterministically in `format.py` from edge data. Only rationale text comes from LLM. Citations and disclaimer are always appended programmatically — never relies on LLM to produce the schema structure.
- **Graceful degradation:** each node wraps external calls in try/except, appends to `errors` list, never crashes
- **Serialization:** all tool results stored as `list[dict]` via `dataclasses.asdict()` for LangSmith tracing
- **Qdrant payload indexes:** created for `metadata.team`, `metadata.teams`, `metadata.season_id`, `metadata.doc_type` to support filtered retrieval

### Files created/modified
- `app/tools/__init__.py` — package init
- `app/agent/__init__.py` — package init
- `app/agent/state.py` — AgentState TypedDict (13 fields)
- `app/agent/prompts.py` — INTENT_SYSTEM_PROMPT, RATIONALE_SYSTEM_PROMPT, FREEFORM_SYSTEM_PROMPT, format helpers
- `app/agent/format.py` — deterministic §8 response builder (build_game_block, build_structured_response, build_citations_block)
- `app/agent/nodes.py` — 6 node functions + helpers (_build_llm_context, _fetch_rationales, _fetch_freeform, _build_citations)
- `app/agent/graph.py` — build_graph() with StateGraph, conditional edge via gate_tavily
- `app/main.py` — /chat wired to compiled graph

## Next step
- Step 11: LangSmith tracing + agent-level eval

## Weekend target
- Complete Steps 8-12 and deploy.
- Keep all work aligned to `AGENTS.md` section 16 (weekend execution mode).
