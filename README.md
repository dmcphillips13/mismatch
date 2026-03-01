# Mismatch

NHL betting edge finder. Compares de-vigged sportsbook odds against Kalshi prediction market prices to surface +EV opportunities.

## Deliverables: [DELIVERABLES.md](DELIVERABLES.md)

**Vercel-Deployed Demo:** https://mismatch-kohl.vercel.app

## Architecture

```
Vercel (web/)                    Render (services/agent/)
┌──────────────┐                 ┌──────────────────────┐
│  Next.js UI  │──/api/chat──▶  │  FastAPI + LangGraph │
│              │◀─────────────  │  (uvicorn)           │
└──────────────┘                 └──────────────────────┘
```

**Agent pipeline:** intent classification → Qdrant retrieval → odds + Kalshi fetch → edge computation → (optional) Tavily news search → response generation

**Data sources:** Odds API (sportsbook lines), Kalshi (prediction markets), Qdrant Cloud (2,251 NHL docs), NHL API (schedules/scores), Tavily (news)

## Local Development

**Setup:**
```bash
# Backend
cd services/agent
cp .env.example .env  # fill in API keys
uv sync

# Frontend
cd ../../web
pnpm install
echo "NEXT_PUBLIC_AGENT_BASE_URL=http://localhost:8000" > .env.local
```

**Run both services:**
```bash
pnpm run start:dev
```

**Or run individually:**
```bash
# Backend
cd services/agent
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd web
pnpm dev
```

## Deployment

- **Frontend:** Vercel — set `NEXT_PUBLIC_AGENT_BASE_URL` to Render URL
- **Backend:** Render — see `render.yaml` blueprint, set API keys in env vars
