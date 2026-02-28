# PROJECT_CONTEXT — Mismatch

## Current completed step
- Step 4 complete (embeddings + Qdrant client + retrieval + data pipeline)

## Current doc setup
- Canonical spec: `AGENTS.md`
- Live handoff: `PROJECT_CONTEXT.md`

## What exists in the repo
- `services/agent/app/main.py` — FastAPI with /health and /chat endpoints
- `services/agent/app/schemas.py` — ChatRequest and ChatResponse models
- `services/agent/app/settings.py` — all env vars including data paths, API base URLs, Cohere
- `services/agent/app/clients/openai_embeddings.py` — EmbeddingClient wrapping text-embedding-3-small (1536 dims)
- `services/agent/app/retrieval/service.py` — RetrievedDocument dataclass with to_citation()
- `services/agent/app/retrieval/qdrant_store.py` — QdrantRetrievalService (ensure_collection, search with filters, upsert_jsonl with batching)
- `services/agent/app/pipeline/build_docs.py` — CSV parsing, rest/b2b computation, team/season summaries, validation logs
- `services/agent/app/utils/team_names.py` — normalize_team_name() + slugify_team_name() with full NHL alias map
- `services/agent/scripts/build_docs.py` — CLI to run pipeline -> docs.jsonl
- `services/agent/scripts/upsert_docs.py` — CLI to upsert docs.jsonl -> Qdrant
- `services/agent/data/processed/docs.jsonl` — 288 docs (32 teams x 3 seasons x 3 doc types)
- `services/agent/pyproject.toml` — all deps including ragas, langchain-openai, langchain-qdrant, langchain-cohere, openevals
- `web/` — Next.js chat UI with /api/chat proxy
- `data/raw/` — 3 NHL season CSVs

## Step 4 verification results
```
$ cd services/agent && uv run python scripts/build_docs.py
wrote 288 docs to data/processed/docs.jsonl
2023-24: total_games=1312
2024-25: total_games=1312
2025-26: total_games=908
back_to_back_rate_distribution=min=0.085,avg=0.149,max=0.196
```
- 288 docs = 32 teams x 3 seasons x 3 doc types (season_summary + last10 + last20)
- Full seasons: 1312 games each (correct)
- 2025-26: 908 games (season in progress, future games with empty scores skipped)
- B2B rate 8.5%-19.6% (sane distribution)
- Payload shape matches AGENTS.md §5 spec exactly

## Open risks/blockers
- **Kalshi API access** — unclear if account is verified; test early
- **All API keys not yet configured** — see dependency readiness below
- **Qdrant Cloud not set up yet** — needed for Step 6 (upsert)

## Dependency readiness
- OpenAI: not-ready
- Qdrant Cloud: not-ready
- Odds API: not-ready
- Kalshi: not-ready
- Tavily: not-ready
- Cohere: not-ready
- LangSmith: not-ready

## Next step
- Step 5-6: Set up Qdrant Cloud, configure .env, run upsert_docs.py
- Then Step 7: RAGAS baseline eval

## Weekend target
- Complete Steps 5-12 and deploy.
- Keep all work aligned to `AGENTS.md` section 16 (weekend execution mode).
