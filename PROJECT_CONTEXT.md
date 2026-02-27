# PROJECT_CONTEXT — Mismatch

## Current completed step
- Step 3 complete (UI proxy + FastAPI skeleton)

## Current doc setup
- Canonical spec: `AGENTS.md`
- Live handoff: `PROJECT_CONTEXT.md`

## What exists in the repo
Committed and working:
- `services/agent/app/main.py` — FastAPI with /health and /chat endpoints
- `services/agent/app/schemas.py` — ChatRequest and ChatResponse models
- `services/agent/app/settings.py` — all env vars including data paths, API base URLs, Cohere
- `services/agent/pyproject.toml` — core deps installed
- `services/agent/.env.example`
- `web/` — Next.js chat UI with /api/chat proxy
- `data/raw/` — 3 NHL season CSVs

## Verification commands
- `cd services/agent && uv run uvicorn app.main:app --reload --port 8000`
- `GET http://localhost:8000/health`
- `POST http://localhost:8000/chat`
- `cd web && pnpm dev`

## Open risks/blockers
- **All Step 4-6 code must be written** — retrieval, pipeline, and upsert modules/scripts are not implemented yet
- **RAGAS eval deps not installed** — `ragas`, `langchain-openai`, `langchain-qdrant`, `langchain-cohere`, `openevals` must be added to pyproject.toml
- **Kalshi API access** — unclear if account is verified; test early
- **All API keys not yet configured** — see dependency readiness below

## Dependency readiness
- OpenAI: not-ready
- Qdrant Cloud: not-ready
- Odds API: not-ready
- Kalshi: not-ready
- Tavily: not-ready
- Cohere: not-ready
- LangSmith: not-ready

## Next step
- Step 4: Implement embeddings client, Qdrant store, retrieval service, team normalization, data pipeline, and scripts
- Then Step 5-6: Run pipeline to produce docs.jsonl, set up Qdrant Cloud, upsert

## Weekend target
- Complete Steps 4-12 and deploy.
- Keep all work aligned to `AGENTS.md` section 16 (weekend execution mode).
