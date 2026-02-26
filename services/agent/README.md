# Mismatch Agent Service (Step 3 Skeleton)

This directory contains the Python FastAPI backend skeleton for Mismatch.

## Install uv

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

## Local setup

```bash
cd services/agent
uv venv
source .venv/bin/activate
uv sync
```

## Run locally

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Test endpoints

- `GET http://localhost:8000/health`
- `POST http://localhost:8000/chat`

Agent logic will be implemented in Step 8.
