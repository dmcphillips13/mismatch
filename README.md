# Mismatch (Clean Start)

Repository layout:
- `web/`: Next.js TypeScript UI (thin client only)
- `services/agent/`: Python FastAPI service placeholder for Step 3
- `archive/root-next-legacy/`: archived legacy root app/code

## Run UI

1. `cd web`
2. `pnpm install`
3. `pnpm dev`

Or from repo root:
- `pnpm dev`

## Environment

Set in `web/.env.local`:
- `NEXT_PUBLIC_AGENT_BASE_URL=http://localhost:8000`
