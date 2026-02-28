# PROJECT_CONTEXT — Mismatch

## Current completed step
- Step 7b complete (H2H matchup docs + rewritten eval questions)

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
- `services/agent/scripts/generate_testset.py` — synthetic + hand-crafted golden dataset generation (uploads to LangSmith)
- `services/agent/scripts/eval_baseline.py` — RAGAS baseline eval (Faithfulness, ContextRecall, ContextEntityRecall, AnswerRelevancy, FactualCorrectness)
- `services/agent/data/processed/docs.jsonl` — 2,251 docs (288 per-team + ~1,467 h2h_season + ~496 h2h_recent)
- `services/agent/data/eval/testset.json` — 10 hand-crafted matchup-focused eval examples
- `services/agent/data/eval/baseline_results.json` — baseline RAGAS scores
- `services/agent/pyproject.toml` — all deps including ragas, rapidfuzz, langchain-openai, langchain-qdrant, langchain-cohere, openevals
- `web/` — Next.js chat UI with /api/chat proxy
- `data/raw/` — 3 NHL season CSVs

## Step 7b baseline RAGAS results (with H2H docs)
```json
{
  "revision_id": "baseline",
  "retrieval": "dense_cosine_qdrant",
  "retrieval_limit": 6,
  "num_examples": 10,
  "metrics": {
    "faithfulness": 0.807,
    "context_recall": 0.850,
    "context_entity_recall": 0.217,
    "answer_relevancy": 0.868
  }
}
```
- Golden dataset: 10 hand-crafted matchup-focused questions (H2H, cross-season, mixed, comparative)
- Doc corpus: 2,251 docs (288 per-team summaries + 1,467 h2h_season + 496 h2h_recent)
- Key improvement vs Step 7: context_recall 0.50 → 0.85 (+70%), answer_relevancy 0.64 → 0.87 (+35%)
- Faithfulness slightly down (0.87 → 0.81) — expected with harder matchup questions
- Context entity recall dropped (0.41 → 0.22) — H2H docs use aggregated stats not raw entity lists
- Next: Cohere rerank (Step 8) should further improve retrieval precision

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
