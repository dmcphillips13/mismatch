"""Minimal FastAPI service skeleton for the Mismatch agent backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import ChatRequest, ChatResponse
from app.settings import settings

app = FastAPI(title="Mismatch Agent Service", version="0.1.0")

if settings.CORS_ORIGINS.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    _ = request
    return ChatResponse(
        answer="Backend skeleton ready.",
        citations=[],
        debug={"note": "Agent not implemented yet"},
    )
