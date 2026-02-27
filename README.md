# Mismatch

This repository contains:
- `web/` — Next.js TypeScript chat UI (thin proxy/client only)
- `services/agent/` — Python FastAPI agent service

## Source of truth

Implementation requirements and execution order live in `AGENTS.md`.
Session-to-session status and blockers live in `PROJECT_CONTEXT.md`.
If this README and `AGENTS.md` differ, follow `AGENTS.md`.

## Local quick start

Frontend:
1. `cd web`
2. `pnpm install`
3. `pnpm dev`

Backend:
1. `cd services/agent`
2. `uv venv`
3. `source .venv/bin/activate`
4. `uv sync`
5. `uv run uvicorn app.main:app --reload --port 8000`

Set in `web/.env.local`:
- `NEXT_PUBLIC_AGENT_BASE_URL=http://localhost:8000`
