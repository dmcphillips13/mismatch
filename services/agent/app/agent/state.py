"""LangGraph agent state definition."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Full state flowing through the Mismatch agent graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    intent: str  # "slate" | "matchup" | "explanation" | "general"
    teams_mentioned: list[str]  # normalized team names from query
    retrieved_docs: list[dict]  # serialized RetrievedDocuments
    retrieved_texts: list[str]  # raw doc texts for LLM context
    odds: list[dict]  # serialized GameOdds
    kalshi_markets: list[dict]  # serialized KalshiMarkets
    matchup_edges: list[dict]  # serialized MatchupEdges
    tavily_results: list[dict]  # serialized TavilyResults (may be empty)
    should_search_news: bool  # Tavily gate flag
    errors: list[str]  # accumulated degradation notes
    answer: str  # final formatted response
    citations: list[dict]  # assembled citations
