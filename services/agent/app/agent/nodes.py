"""LangGraph node functions for the Mismatch agent pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from openai import OpenAI

from app.agent.format import build_structured_response
from app.agent.prompts import (
    FREEFORM_SYSTEM_PROMPT,
    INTENT_SYSTEM_PROMPT,
    RATIONALE_SYSTEM_PROMPT,
    format_edges_for_prompt,
    format_tavily_for_prompt,
)
from app.agent.state import AgentState
from app.retrieval.qdrant_store import QdrantRetrievalService
from app.settings import settings
from app.tools.kalshi import KalshiClient
from app.tools.match import build_matchup_edges
from app.tools.models import GameOdds, KalshiMarket
from app.tools.odds_api import OddsAPIClient
from app.tools.tavily import TavilyClient
from app.utils.team_names import normalize_team_name

logger = logging.getLogger(__name__)

_EXPLANATION_KEYWORDS = {"why", "injury", "goalie", "news", "explain", "injured", "status"}


def _get_llm() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _user_query(state: AgentState) -> str:
    """Extract the latest user message text from state."""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            return msg.content
        if hasattr(msg, "role") and msg.role == "user":
            return msg.content
    return ""


# ---------------------------------------------------------------------------
# Node 1: interpret_intent
# ---------------------------------------------------------------------------

def interpret_intent(state: AgentState) -> dict[str, Any]:
    """Classify user intent and extract team names via LLM."""
    query = _user_query(state)
    errors: list[str] = list(state.get("errors", []))

    try:
        client = _get_llm()
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        parsed = json.loads(raw)
        intent = parsed.get("intent", "slate")
        teams_raw = parsed.get("teams", [])
        teams = [normalize_team_name(t) for t in teams_raw]
    except Exception as exc:
        logger.warning("Intent classification failed: %s", exc)
        errors.append(f"Intent classification failed: {exc}")
        intent = "slate"
        teams = []

    # Check for explanation keywords in query as fallback
    query_lower = query.lower()
    if intent != "explanation" and any(kw in query_lower for kw in _EXPLANATION_KEYWORDS):
        intent = "explanation"

    return {
        "intent": intent,
        "teams_mentioned": teams,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 2: retrieve
# ---------------------------------------------------------------------------

def retrieve(state: AgentState) -> dict[str, Any]:
    """Retrieve relevant documents from Qdrant."""
    query = _user_query(state)
    teams = state.get("teams_mentioned", [])
    errors: list[str] = list(state.get("errors", []))

    try:
        service = QdrantRetrievalService()
        try:
            docs = service.search(query, limit=6, teams=teams if teams else None)
        except Exception:
            if teams:
                logger.warning("Filtered retrieval failed, retrying without team filter")
                docs = service.search(query, limit=6)
            else:
                raise
        retrieved_docs = [asdict(d) for d in docs]
        retrieved_texts = [d.text for d in docs]
    except Exception as exc:
        logger.warning("Qdrant retrieval failed: %s", exc)
        errors.append(f"Qdrant retrieval failed: {exc}")
        retrieved_docs = []
        retrieved_texts = []

    return {
        "retrieved_docs": retrieved_docs,
        "retrieved_texts": retrieved_texts,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 3: fetch_odds_and_kalshi
# ---------------------------------------------------------------------------

def fetch_odds_and_kalshi(state: AgentState) -> dict[str, Any]:
    """Fetch odds from Odds API and markets from Kalshi."""
    errors: list[str] = list(state.get("errors", []))
    odds: list[dict] = []
    kalshi_markets: list[dict] = []

    # Odds API
    try:
        odds_client = OddsAPIClient()
        odds_results = odds_client.fetch_nhl_odds()
        odds = [asdict(o) for o in odds_results]
    except Exception as exc:
        logger.warning("Odds API failed: %s", exc)
        errors.append(f"Odds API failed: {exc}")

    # Kalshi
    try:
        kalshi_client = KalshiClient()
        kalshi_results = kalshi_client.fetch_nhl_markets()
        kalshi_markets = [asdict(m) for m in kalshi_results]
    except Exception as exc:
        logger.warning("Kalshi API failed: %s", exc)
        errors.append(f"Kalshi API failed: {exc}")

    return {
        "odds": odds,
        "kalshi_markets": kalshi_markets,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 4: compute_edges
# ---------------------------------------------------------------------------

def compute_edges(state: AgentState) -> dict[str, Any]:
    """Compute matchup edges and set Tavily gate flag."""
    errors: list[str] = list(state.get("errors", []))
    odds_dicts = state.get("odds", [])
    kalshi_dicts = state.get("kalshi_markets", [])
    intent = state.get("intent", "slate")
    query = _user_query(state)

    try:
        # Reconstruct dataclass instances from dicts
        odds_objs = [GameOdds(**o) for o in odds_dicts]
        kalshi_objs = [KalshiMarket(**m) for m in kalshi_dicts]
        edges = build_matchup_edges(odds_objs, kalshi_objs)
        matchup_edges = [asdict(e) for e in edges]
    except Exception as exc:
        logger.warning("Edge computation failed: %s", exc)
        errors.append(f"Edge computation failed: {exc}")
        matchup_edges = []

    # Tavily gating: search if any BET recommendation or explanation intent
    has_bet = any(e.get("recommendation") == "BET" for e in matchup_edges)
    query_lower = query.lower()
    has_keywords = any(kw in query_lower for kw in _EXPLANATION_KEYWORDS)
    should_search = has_bet or intent == "explanation" or has_keywords

    return {
        "matchup_edges": matchup_edges,
        "should_search_news": should_search,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 5: tavily_search
# ---------------------------------------------------------------------------

def tavily_search(state: AgentState) -> dict[str, Any]:
    """Search for relevant NHL news via Tavily."""
    teams = state.get("teams_mentioned", [])
    intent = state.get("intent", "slate")
    errors: list[str] = list(state.get("errors", []))

    # Build search query from teams and intent
    if teams:
        search_query = f"NHL {' '.join(teams)} injuries goalie news today"
    elif intent == "explanation":
        query = _user_query(state)
        search_query = f"NHL {query}"
    else:
        search_query = "NHL injuries goalie news today"

    try:
        client = TavilyClient()
        results = client.search(search_query, max_results=5)
        tavily_results = [asdict(r) for r in results]
    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        errors.append(f"Tavily search failed: {exc}")
        tavily_results = []

    return {
        "tavily_results": tavily_results,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 6: generate_response
# ---------------------------------------------------------------------------

def generate_response(state: AgentState) -> dict[str, Any]:
    """Generate the final response using all gathered data.

    For slate/matchup intents: game blocks are built deterministically from
    edge data. Only the rationale text comes from the LLM.
    For explanation/general intents: LLM produces freeform text, then
    citations and disclaimer are appended programmatically.
    """
    query = _user_query(state)
    intent = state.get("intent", "slate")
    retrieved_texts = state.get("retrieved_texts", [])
    matchup_edges = state.get("matchup_edges", [])
    tavily_results = state.get("tavily_results", [])
    retrieved_docs = state.get("retrieved_docs", [])
    errors: list[str] = list(state.get("errors", []))

    # For matchup intent, filter edges to only the mentioned teams
    teams = state.get("teams_mentioned", [])
    display_edges = matchup_edges
    if intent == "matchup" and teams:
        teams_lower = {t.lower() for t in teams}
        display_edges = [
            e for e in matchup_edges
            if e.get("home_team", "").lower() in teams_lower
            or e.get("away_team", "").lower() in teams_lower
        ]
        if not display_edges:
            # Requested matchup not on today's slate
            errors = list(errors)
            errors.append(
                f"No active market found for {' vs '.join(teams)}. "
                "The game may not be scheduled today."
            )

    # Build shared context for the LLM
    context = _build_llm_context(
        retrieved_texts, display_edges, tavily_results, errors
    )

    rationales: dict[str, str] = {}
    freeform_text = ""

    if intent in ("slate", "matchup"):
        rationales = _fetch_rationales(query, context, display_edges)
    else:
        freeform_text = _fetch_freeform(query, context)

    # Assemble response deterministically
    answer = build_structured_response(
        intent=intent,
        edges=display_edges,
        rationales=rationales,
        retrieved_docs=retrieved_docs,
        tavily_results=tavily_results,
        errors=errors,
        freeform_text=freeform_text,
    )

    # Build structured citations for the API response
    citations = _build_citations(retrieved_docs, matchup_edges, tavily_results)

    return {
        "answer": answer,
        "citations": citations,
    }


def _build_llm_context(
    retrieved_texts: list[str],
    matchup_edges: list[dict],
    tavily_results: list[dict],
    errors: list[str],
) -> str:
    """Assemble context sections for the LLM prompt."""
    parts: list[str] = []

    if retrieved_texts:
        parts.append("Retrieved context from historical data:")
        for i, text in enumerate(retrieved_texts, 1):
            parts.append(f"[Doc {i}] {text[:500]}")
    else:
        parts.append("No historical context available from Qdrant.")

    parts.append("\nMatchup edge data:")
    parts.append(format_edges_for_prompt(matchup_edges))

    tavily_text = format_tavily_for_prompt(tavily_results)
    if tavily_text:
        parts.append(f"\n{tavily_text}")

    if errors:
        parts.append("\nDegraded data notes:")
        for err in errors:
            parts.append(f"- {err}")

    return "\n".join(parts)


def _fetch_rationales(
    query: str, context: str, edges: list[dict]
) -> dict[str, str]:
    """Ask LLM for rationale text per game, return as dict keyed by game."""
    game_keys = [
        f"{e['away_team']} @ {e['home_team']}"
        for e in edges
        if e.get("recommendation") != "NO_MARKET"
    ]
    if not game_keys:
        return {}

    prompt = (
        f"User query: {query}\n\n{context}\n\n"
        f"Games to provide rationales for:\n"
        + "\n".join(f"- {k}" for k in game_keys)
    )

    try:
        client = _get_llm()
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": RATIONALE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        parsed = json.loads(raw)
        return parsed.get("rationales", {})
    except Exception as exc:
        logger.warning("Rationale generation failed: %s", exc)
        return {k: "Analysis unavailable." for k in game_keys}


def _fetch_freeform(query: str, context: str) -> str:
    """Ask LLM for freeform text (explanation/general intents)."""
    try:
        client = _get_llm()
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": FREEFORM_SYSTEM_PROMPT},
                {"role": "user", "content": f"User query: {query}\n\n{context}"},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Freeform generation failed: %s", exc)
        return "I encountered an error generating a response. Please try again."


def _build_citations(
    retrieved_docs: list[dict],
    matchup_edges: list[dict],
    tavily_results: list[dict],
) -> list[dict]:
    """Build structured citation dicts for the API response."""
    citations: list[dict] = []

    # Qdrant doc citations
    for doc in retrieved_docs:
        meta = doc.get("metadata", {})
        teams_list = meta.get("teams")
        if teams_list and isinstance(teams_list, list) and len(teams_list) >= 2:
            label = f"{teams_list[0]} vs {teams_list[1]}"
        else:
            label = meta.get("team", "Unknown")
        citations.append({
            "id": doc.get("id", ""),
            "label": label,
            "season_id": meta.get("season_id"),
            "doc_type": meta.get("doc_type"),
            "source": "qdrant",
        })

    # Odds API citation
    if matchup_edges:
        citations.append({
            "id": "odds-api",
            "label": "Odds API",
            "source": "odds_api",
        })

    # Tavily citations
    for r in tavily_results:
        citations.append({
            "id": r.get("url", ""),
            "label": r.get("title", "Tavily"),
            "source": "tavily",
            "url": r.get("url", ""),
        })

    return citations
