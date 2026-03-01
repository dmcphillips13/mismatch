"""LangGraph StateGraph construction for the Mismatch agent."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    compute_edges,
    fetch_odds_and_kalshi,
    generate_response,
    interpret_intent,
    retrieve,
    tavily_search,
)
from app.agent.state import AgentState


def _gate_tavily(state: AgentState) -> str:
    """Conditional edge: route to Tavily search or skip to response."""
    if state.get("should_search_news", False):
        return "tavily_search"
    return "generate_response"


def build_graph():
    """Construct and compile the Mismatch agent graph.

    Graph shape:
        START -> interpret_intent -> retrieve -> fetch_odds_and_kalshi
            -> compute_edges -> [gate] -> tavily_search? -> generate_response -> END
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("interpret_intent", interpret_intent)
    graph.add_node("retrieve", retrieve)
    graph.add_node("fetch_odds_and_kalshi", fetch_odds_and_kalshi)
    graph.add_node("compute_edges", compute_edges)
    graph.add_node("tavily_search", tavily_search)
    graph.add_node("generate_response", generate_response)

    # Wire linear edges
    graph.set_entry_point("interpret_intent")
    graph.add_edge("interpret_intent", "retrieve")
    graph.add_edge("retrieve", "fetch_odds_and_kalshi")
    graph.add_edge("fetch_odds_and_kalshi", "compute_edges")

    # Conditional edge from compute_edges: Tavily gate
    graph.add_conditional_edges(
        "compute_edges",
        _gate_tavily,
        {
            "tavily_search": "tavily_search",
            "generate_response": "generate_response",
        },
    )

    # Tavily -> response -> END
    graph.add_edge("tavily_search", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()
