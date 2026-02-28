# PROJECT_CONTEXT — Mismatch

## Current completed step
- Step 8 complete (Cohere rerank + RAGAS comparison eval)

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
- `services/agent/app/utils/team_names.py` — normalize_team_name() + slugify_team_name() with full NHL alias map
- `services/agent/app/eval/__init__.py` — eval package
- `services/agent/app/eval/rag_chain.py` — baseline + reranked RAG chains for RAGAS eval (RAGResult with token usage tracking)
- `services/agent/app/eval/helpers.py` — shared eval utilities (metrics, cost estimation, LangSmith upload)
- `services/agent/app/retrieval/reranker.py` — CohereRerank + ContextualCompressionRetriever (retrieve 10, rerank to 5)
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

## Dependency readiness
- OpenAI: ready
- Qdrant Cloud: ready (2,251 docs upserted to mismatch_docs collection)
- LangSmith: ready (golden dataset uploaded)
- Odds API: not-ready
- Kalshi: not-ready
- Tavily: not-ready
- Cohere: ready (rerank-v3.5, trial key with 10 req/min rate limit)

## Next step
- Step 9: LangGraph agent with tools

## Weekend target
- Complete Steps 8-12 and deploy.
- Keep all work aligned to `AGENTS.md` section 16 (weekend execution mode).
