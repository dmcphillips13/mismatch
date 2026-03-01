"""FastAPI service for the Mismatch agent backend."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage

from app.agent.graph import build_graph
from app.schemas import ChatRequest, ChatResponse
from app.settings import settings

logger = logging.getLogger(__name__)

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

# Compile the graph once at startup
agent_graph = build_graph()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Run the Mismatch agent graph and return a structured response."""
    try:
        # Convert ChatMessage list to LangChain messages
        messages = []
        for msg in request.messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))

        # Initialize state with messages and empty defaults
        initial_state = {
            "messages": messages,
            "intent": "",
            "teams_mentioned": [],
            "retrieved_docs": [],
            "retrieved_texts": [],
            "odds": [],
            "kalshi_markets": [],
            "matchup_edges": [],
            "tavily_results": [],
            "should_search_news": False,
            "errors": [],
            "answer": "",
            "citations": [],
        }

        result = agent_graph.invoke(initial_state)

        return ChatResponse(
            answer=result.get("answer", "No response generated."),
            citations=result.get("citations", []),
            debug={
                "intent": result.get("intent", ""),
                "teams_mentioned": result.get("teams_mentioned", []),
                "num_edges": len(result.get("matchup_edges", [])),
                "tavily_used": bool(result.get("tavily_results")),
                "errors": result.get("errors", []),
            },
        )

    except Exception as exc:
        logger.exception("Agent graph failed")
        return ChatResponse(
            answer=(
                "I encountered an unexpected error processing your request. "
                "Please try again.\n\n"
                "Disclaimer: Not financial advice."
            ),
            citations=[],
            debug={"error": str(exc)},
        )
