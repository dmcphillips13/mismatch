# AGENTS.md — Mismatch (Source of Truth for Codex/Agents)

This file is the **single source of truth** for building **Mismatch**.  
All agents (Codex, Claude Code, Cursor, etc.) should follow this document to avoid drift.

---

## Doc roles

- `AGENTS.md`: canonical product + engineering contract.
- `PROJECT_CONTEXT.md`: current status/handoff between sessions.

---

## 0) One-line mission

**Mismatch** is a chat-based assistant that recommends **BET / PASS** for **Kalshi NHL moneyline (head-to-head)** markets by comparing **Kalshi implied probability** to a **de‑vigged sportsbook “fair” probability** (from an odds aggregator).

This is a **discrepancy detector** + **RAG justification** app — **not** a predictive model.

---

## 1) Current repo layout and ownership

### Frontend (TypeScript only)
- Location: `web/`
- Framework: Next.js App Router (TS)
- Purpose: Chat UI + thin proxy to backend
- **Rule:** No agent logic in TS. No embeddings. No Qdrant. No Tavily. No odds math. No LLM calls.

**Backend URL env:**
- `web/.env.local` (not committed) must define:
  - `NEXT_PUBLIC_AGENT_BASE_URL=http://localhost:8000` (dev)
  - Vercel uses same variable pointing to deployed backend.

### Backend (Python only)
- Location: `services/agent/`
- Framework: FastAPI
- Dependency manager: **uv** (pyproject + uv.lock)
- Purpose: Agent, tools, retrieval, evaluation.

#### Required dependencies (pyproject.toml)
Core (already present): `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `python-dotenv`, `httpx`, `qdrant-client`, `langchain`, `langgraph`, `langsmith`, `openai`

Must add at the start of Step 4 (before any implementation begins):
- `ragas` — evaluation framework (cert Tasks 5 & 6)
- `langchain-openai` — LangChain wrappers needed by RAGAS
- `langchain-qdrant` — LangChain-compatible Qdrant retriever for RAGAS eval
- `langchain-cohere` — Cohere reranking for advanced retrieval (cert Task 6)
- `openevals` — LLM-as-judge evaluators (AIE9 pattern)

### Data (repo-level)
- Location: `data/raw/`
- Input CSVs:
  - `nhl-202324-asplayed.csv`
  - `nhl-202425-asplayed.csv`
  - `nhl-202526-asplayed.csv`
- Backend pipeline outputs should live under:
  - `services/agent/data/processed/docs.jsonl`

---

## 2) Product scope (certification-first)

### Must support
- Queries for **today through 7 days out**
- NHL **moneyline** only (head-to-head winner)
- More than one question — general NHL market Q&A is allowed, but recommendations are only for moneyline markets

### Must NOT support (for now)
- Player props
- Parlays
- Futures
- Live/in-game betting

### UX
- Chat-only UI (no dashboards required)
- Show citations under answers

---

## 3) Core method: discrepancy detection (no modeling)

### Primary user question
> “What NHL games are +EV on Kalshi?”  
and follow-ups like  
> “Is X vs Y +EV? Why?” / “Any injury updates?” / “What changed?”

### Decision rule
1) Get **fair probability** from odds aggregator (de-vigged).
2) Get **Kalshi implied probability** for same matchup.
3) Compute:
   - `edge = fair_prob - kalshi_prob`
4) Recommend:
- **BET** if `edge >= EDGE_THRESHOLD`
- **PASS** otherwise

### Explicit assumption to document
- Odds aggregator fair line is treated as the reference (“market consensus”).
- Kalshi mismatch is the signal.
- This is *not* financial advice.

---

## 4) Tools + tool-calling policy (hard rules)

### Tools
Backend must implement deterministic tools (no LLM calls inside tools):
1) **Odds aggregator** (e.g., the-odds-api)
   - Fetch moneyline odds for NHL games (today..+7 days)
   - Convert American odds -> implied probabilities
   - De-vig to fair probabilities
2) **Kalshi**
   - Fetch Kalshi markets for NHL moneyline
   - Map matchups deterministically (team normalization)
   - Return implied probabilities
3) **Tavily**
   - Web search for injuries/goalies/news context

### Tool calling rules (non-negotiable)
- **Always retrieve from Qdrant first** (RAG-first) before calling tools.
- Call **Odds API** and **Kalshi** for any recommendation request.
- Call **Tavily only if:**
  - `edge >= EDGE_THRESHOLD`, **OR**
  - user explicitly asks for explanation/news (“why”, “injury”, “goalie”, “news”, “explain”)
- Degrade gracefully:
  - If Kalshi match fails for a game: skip it and explain in debug/citations
  - If Tavily fails: proceed without it
  - If Qdrant is down: proceed with tools but note “no RAG context available”

---

## 5) RAG / Qdrant strategy

### What goes into Qdrant
- Pre-generated **team season summaries** and **rolling form summaries**
- Computed rest/back-to-back metrics
- Optional: goalie/travel notes if present, but keep stable and deterministic

### Embeddings
- OpenAI embeddings model: `text-embedding-3-small` (1536 dims)

### LLM defaults
- App generation/model routing default: `gpt-4o-mini`
- Evaluation/judge model default: `gpt-4o-mini`

### Qdrant payload shape (must be consistent)
Each point payload MUST be:
```json
{
  "text": "...document text...",
  "metadata": {
    "team": "...",
    "season_id": "2023-24",
    "doc_type": "team_season_summary",
    "date_range": "YYYY-MM-DD to YYYY-MM-DD",
    "created_at": "...",
    "game_count": 82
  }
}
```

### Filter fields (must work)
- `metadata.team` (exact match)
- `metadata.season_id` (exact match)
- `metadata.doc_type` (IN list)

### Season partitioning (critical)
Never treat 3 seasons as one mega-season.
- All summaries computed per `(team, season_id)`
- `season_id` derived from filename (see §6)

### Qdrant hosting
- Use **Qdrant Cloud** (free tier, 1GB) for both dev and deployed environments.
- Set `QDRANT_URL` and `QDRANT_API_KEY` in `.env` / deployment secrets.

### Baseline retrieval
- Dense vector cosine similarity via Qdrant (this is the baseline for cert Task 5 eval).

### Advanced retrieval (cert Task 6)
After baseline eval, implement **Cohere reranking** as the advanced retrieval upgrade:
- Use `langchain_cohere.CohereRerank` with `rerank-v3.5`
- Wrap existing Qdrant retriever with `ContextualCompressionRetriever`
- Retrieve top-k (e.g., 10) from Qdrant, rerank down to top 5
- Re-evaluate with RAGAS to quantify improvement vs baseline
- This layers on top of existing Qdrant search — no pipeline changes needed

---

## 6) Data pipeline rules (CSV -> docs.jsonl)

### Inputs
Use CSVs under `data/raw/`. Column differences across seasons are expected.
- Ignore 2025-26 “historical odds” columns for modeling (may exist, but not used).

### Season id derivation (source of truth)
From filename:
- `nhl-202324-asplayed.csv` -> `2023-24`
- `nhl-202425-asplayed.csv` -> `2024-25`
- `nhl-202526-asplayed.csv` -> `2025-26`

### Normalization
Build normalized game records:
- `season_id`
- `date` (YYYY-MM-DD)
- `home_team`, `away_team`
- `home_goals`, `away_goals`
- `status` (Regulation/OT/SO if available)

### Rest / back-to-back (critical correctness)
Compute per **team** and per **season**:
- Team-game list includes games where team is home OR away
- Sort by date for that team-season
- `rest_days = date_i - date_{i-1} (days)`
- `back_to_back = (rest_days == 1)`
- First game: `rest_days = null`, `back_to_back = false`

### Required summaries
For each `(team, season_id)` generate:
- `team_season_summary`
- `team_form_summary_last10`
- `team_form_summary_last20`

### Required validation logs
- Per season: total games ~1312
- Per team-season: game_count around 82; warn if > 100
- Back-to-back rate distribution should be sane (not all true)

---

## 7) Agent behavior (LangGraph)

### Orchestration order (must follow)
1) Interpret intent (slate discovery vs matchup check vs explanation)
2) **Retrieve from Qdrant** (always)
3) Call **Odds API**
4) Call **Kalshi**
5) Compute edge + decision
6) Conditionally call **Tavily** per policy
7) Produce response with citations

### Degrade gracefully
Agent must never crash on a tool failure.
Return a safe response with whatever data is available and explain limitations.

---

## 8) Response format (strict)

All assistant responses MUST follow this schema:

```
Recommendation: BET / PASS
Game:
Kalshi Probability:
Fair Probability (de-vigged):
Edge:
Rationale:
Citations:
Disclaimer: Not financial advice.
```

### Citations requirements
Citations must include:
- Qdrant doc ids used (and metadata season_id/doc_type)
- Odds API as a source (at least “Odds API” label; URLs if available)
- Tavily links if Tavily used

---

## 9) Evaluation (RAGAS + LangSmith)

### Framework
- **RAGAS** is the evaluation framework (required by certification).
- **LangSmith** is used for tracing all agent runs and hosting eval datasets.

### Evaluator LLM
- Use `gpt-4o-mini` as the RAGAS evaluator LLM (via `LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))`)
- Same model for `openevals` LLM-as-judge evaluators

### RAGAS metrics (required for cert Tasks 5 & 6)
Baseline eval (Task 5) must report at minimum:
- `Faithfulness` — is the response grounded in retrieved context? (most important)
- `LLMContextRecall` — what % of reference context is retrieved?
- `ContextEntityRecall` — are key entities from context present in the response?
- `ResponseRelevancy` — how relevant is the response to the question?
- `FactualCorrectness` — is the response factually accurate?

Advanced retrieval eval (Task 6) must re-run the same metrics after upgrade and compare in a table.

### Additional evaluators (app-specific)
- Format correctness (response matches §8 schema)
- Citation coverage (Qdrant doc ids, Odds API label, Tavily links present)
- Tool policy compliance (Tavily gating)
- Threshold consistency (BET iff edge >= threshold)
- These can use `openevals.llm.create_llm_as_judge` or custom Python checks.

### Agent-level metrics (optional but recommended)
If time permits, evaluate agent traces with:
- `ToolCallAccuracy` — did agent call the correct tools with correct args?
- `AgentGoalAccuracyWithReference` — did agent achieve the user's goal?
- `TopicAdherenceScore` — did agent stay on NHL betting topics?

Use `ragas.integrations.langgraph.convert_to_ragas_messages` to convert LangGraph traces to RAGAS format.

### Synthetic dataset generation
Use `ragas.testset.TestsetGenerator` to generate the golden dataset from `docs.jsonl` documents:
- Wrap models with `LangchainLLMWrapper` and `LangchainEmbeddingsWrapper`
- Target ~50 examples with mixed query distribution:
  - `SingleHopSpecificQuerySynthesizer` (50%) — factual team lookups
  - `MultiHopAbstractQuerySynthesizer` (25%) — cross-team reasoning
  - `MultiHopSpecificQuerySynthesizer` (25%) — cross-team factual
- Supplement with ~10 hand-crafted questions matching real use cases (e.g., "Which team has the best back-to-back record?", "Is Team X vs Team Y +EV?") since the formulaic doc summaries may produce shallow synthetic questions
- Upload generated dataset to LangSmith via `client.create_dataset()`

### LangSmith
- Use LangSmith tracing for all agent runs
- Prefer a single project: `mismatch`
- Tag eval runs with `metadata={"revision_id": "baseline"}` or `"advanced_retrieval"` for comparison

---

## 10) Deployment expectations

### Frontend (Vercel)
- Deploy `web/`
- Configure `NEXT_PUBLIC_AGENT_BASE_URL`

### Backend (Render/Fly/Railway)
- Deploy `services/agent/`
- Start command (uv, no docker):
  - `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## 11) Repo hygiene (important)

The following should NOT be committed:
- `web/node_modules/`
- `web/.next/`
- `services/agent/.venv/`
- `__pycache__/`, `*.pyc`
- `.pnpm-store/` (should not be in repo)
- `web/.env.local`

`.env.example` files SHOULD be committed:
- `web/.env.example`
- `services/agent/.env.example`

---

## 12) How to work with Codex (process rules)

When making changes:
1) Make one step at a time.
2) List files changed/created.
3) Provide commands to run to verify.
4) Do not refactor unrelated parts.
5) If uncertain, prefer adding small validation logs over complex abstractions.

---

## 13) Immediate next steps (as of now)

1) Step 4: Implement embeddings + Qdrant client + retrieval in Python
2) Step 5: Implement Python data pipeline to produce docs.jsonl
3) Step 6: Upsert docs to Qdrant
4) Step 7: RAGAS baseline eval — generate synthetic dataset, run retrieval-only eval, record baseline metrics (cert Task 5)
5) Step 8: Advanced retrieval — add Cohere reranking, re-eval with RAGAS, compare to baseline (cert Task 6)
6) Step 9: Implement tools (Odds API, Kalshi, Tavily) + odds math
7) Step 10: Implement LangGraph agent + strict schema output
8) Step 11: LangSmith tracing + agent-level eval
9) Step 12: Deploy backend + frontend, end-to-end checks

---

## 14) Certification alignment (AIE9 patterns, app-first)

Mismatch is implemented as a deployed app, not as notebooks.
Development mirrors the AIE9 curriculum structure:

- **Session 02 pattern** (Dense Vector Retrieval): `text-embedding-3-small` + Qdrant cosine similarity as baseline.
- **Session 04 pattern** (Agentic RAG): LangGraph `StateGraph` with `@tool` decorator, `ToolNode`, conditional routing.
- **Session 05 pattern** (Multi-Agent LangGraph): State as `TypedDict`, `add_messages` reducer, supervisor routing.
- **Session 09 pattern** (Synthetic Data): `ragas.testset.TestsetGenerator` for golden dataset, upload to LangSmith.
- **Session 10 pattern** (RAGAS Eval): `ragas.evaluate()` with `EvaluationDataset`, `LangchainLLMWrapper`, `RunConfig`.
- **Session 11 pattern** (Advanced Retrieval): `CohereRerank` + `ContextualCompressionRetriever` layered on base retriever.

Core principles:
- Baseline first, then one controlled upgrade (reranking), then re-evaluate with RAGAS.
- Keep components explicit and testable: retrieval, tools, orchestration, eval.
- Preserve reproducible evaluation scripts and outputs for write-up/demo.
- Keep architecture simple unless evidence from evals justifies added complexity.

Practical interpretation for this repo:
- Use AIE9 notebook patterns as references; implement all production logic in `services/agent/` Python modules/scripts.
- Use LangChain wrappers (`langchain_openai`, `langchain_qdrant`) where needed for RAGAS compatibility.
- Keep frontend as thin TS chat UI only.

---

## 15) Session continuity requirements

To preserve context across many Codex sessions, each substantial implementation step should update a short status log file at repo root:
- `PROJECT_CONTEXT.md`

`PROJECT_CONTEXT.md` should include:
1) Current completed step
2) Files touched in that step
3) Commands used to verify
4) Open risks/blockers
5) Next step

This file is operational context, not product copy.

---

## 16) Weekend execution mode (for Codex + Claude Code)

Objective: ship a certification-ready deployed app this weekend without scope creep.

Execution order: follow §13 (Steps 4-12). That is the canonical step list — do not duplicate here.

Rules during weekend sprint:
- One step at a time; do not begin next step before verification.
- Always report: files changed, commands run, success criteria met.
- Keep diffs small and reversible; no unrelated refactors.
- If blocked by API/network, implement graceful fallback + clear debug notes, then continue.
- Keep frontend thin; all intelligence remains in Python backend.

Definition of done for weekend:
- End-to-end deployed chat works (Vercel -> FastAPI backend).
- Recommendations follow strict schema and include required citations.
- Tavily gating policy enforced.
- LangSmith traces visible under project `mismatch`.
- RAGAS baseline eval report generated (cert Task 5).
- Advanced retrieval comparison table generated (cert Task 6).
- Eval dataset (~50 examples) generated and uploaded to LangSmith.

---

## 17) Session start template

At the start of each new Codex/Claude session, provide this block:

```
Current step: <number + title>
Goal for this session: <single step outcome>
Completed previously: <1-3 bullets>
Blockers: <keys/services/env blockers, or "none">
Environment status:
- OpenAI: ready/not-ready
- Qdrant: ready/not-ready
- Odds API: ready/not-ready
- Kalshi: ready/not-ready
- Tavily: ready/not-ready
- Cohere: ready/not-ready
- LangSmith: ready/not-ready
Verification target:
- command(s) to run
- success criteria
```

Agents should then execute only that step unless explicitly asked to re-scope.
