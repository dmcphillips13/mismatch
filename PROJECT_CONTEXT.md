# PROJECT_CONTEXT — Mismatch

## Current completed step
- Step 7 complete (H2H matchup docs + RAGAS synthetic testset + baseline eval)

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
- `services/agent/app/eval/rag_chain.py` — simple retrieve+generate chain for RAGAS eval (RAGResult dataclass)
- `services/agent/scripts/build_docs.py` — CLI to run pipeline -> docs.jsonl
- `services/agent/scripts/upsert_docs.py` — CLI to upsert docs.jsonl -> Qdrant
- `services/agent/scripts/generate_testset.py` — RAGAS TestsetGenerator with doc sampling, static personas, and retry logic (uploads to LangSmith)
- `services/agent/scripts/eval_baseline.py` — RAGAS baseline eval (Faithfulness, ContextRecall, ContextEntityRecall, AnswerRelevancy, FactualCorrectness)
- `services/agent/data/processed/docs.jsonl` — 2,251 docs (288 per-team + ~1,467 h2h_season + ~496 h2h_recent)
- `services/agent/data/eval/testset.json` — 51 synthetic eval examples (RAGAS TestsetGenerator, ~50 target)
- `services/agent/data/eval/baseline_results.json` — baseline RAGAS scores
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
    "faithfulness": 0.820,
    "context_recall": 0.712,
    "context_entity_recall": 0.356,
    "answer_relevancy": 0.640
  }
}
```
- Golden dataset: 51 synthetic examples via RAGAS TestsetGenerator (SingleHop 50%, MultiHopAbstract 25%, MultiHopSpecific 25%)
- Synthetic generation uses stratified doc sampling (100 of 2,251 docs) and static personas
- Doc corpus: 2,251 docs (288 per-team summaries + 1,467 h2h_season + 496 h2h_recent)
- Next: Cohere rerank (Step 8) should improve retrieval precision

## Dependency readiness
- OpenAI: ready
- Qdrant Cloud: ready (2,251 docs upserted to mismatch_docs collection)
- LangSmith: ready (golden dataset uploaded)
- Odds API: not-ready
- Kalshi: not-ready
- Tavily: not-ready
- Cohere: not-ready

## Next step
- Step 8: Advanced retrieval (Cohere rerank) + RAGAS comparison eval
- Then Step 9: LangGraph agent with tools

## Weekend target
- Complete Steps 8-12 and deploy.
- Keep all work aligned to `AGENTS.md` section 16 (weekend execution mode).
