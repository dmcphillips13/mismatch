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
from app.tools.nhl_api import NHLScoreClient
from app.tools.odds_api import OddsAPIClient
from app.tools.tavily import TavilyClient
from app.utils.team_names import normalize_team_name, team_name_to_abbrev

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
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        parsed = json.loads(raw)
        intent = parsed.get("intent", "slate")
        ev_only = parsed.get("ev_only", False)
        teams_raw = parsed.get("teams", [])
        teams = [normalize_team_name(t) for t in teams_raw]
    except Exception as exc:
        logger.warning("Intent classification failed: %s", exc)
        errors.append(f"Intent classification failed: {exc}")
        intent = "slate"
        ev_only = False
        teams = []

    # Check for explanation keywords in query as fallback
    query_lower = query.lower()
    if intent != "explanation" and any(kw in query_lower for kw in _EXPLANATION_KEYWORDS):
        intent = "explanation"

    return {
        "intent": intent,
        "ev_only": ev_only,
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
        season_filter = [settings.CURRENT_SEASON, "all"]
        try:
            docs = service.search(
                query, limit=6, teams=teams if teams else None,
                season_ids=season_filter,
            )
        except Exception:
            if teams:
                logger.warning("Filtered retrieval failed, retrying without team filter")
                docs = service.search(query, limit=6, season_ids=season_filter)
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

    # Fetch NHL live scores and attach game_status to each edge
    try:
        scores = NHLScoreClient().fetch_live_scores()
        score_lookup: dict[tuple[str, str], dict] = {}
        for s in scores:
            score_lookup[(s.away_abbrev, s.home_abbrev)] = asdict(s)

        for edge in matchup_edges:
            away_abbrev = team_name_to_abbrev(edge["away_team"]) or ""
            home_abbrev = team_name_to_abbrev(edge["home_team"]) or ""
            game_score = score_lookup.get((away_abbrev, home_abbrev))
            if game_score:
                edge["game_status"] = game_score
    except Exception as exc:
        logger.warning("NHL score fetch failed: %s", exc, exc_info=True)

    # NHL-as-source-of-truth: for mentioned teams, always fetch the real
    # next game from the NHL API and reconcile with existing betting edges.
    teams = list(state.get("teams_mentioned", []))
    logger.info("[SCHED] teams_mentioned from state: %s", teams)

    # Fallback: if the intent classifier didn't extract teams, scan the
    # query for known abbreviations (e.g. "CBJ", "NYR") so schedule
    # queries like "What is CBJ's next game?" still work.
    if not teams:
        for word in query.split():
            cleaned = word.strip("'s?.!,").upper()
            resolved = normalize_team_name(cleaned)
            if resolved != cleaned and team_name_to_abbrev(resolved):
                teams.append(resolved)
        logger.info("[SCHED] fallback extracted teams: %s", teams)
    if teams:
        for team in teams:
            abbrev = team_name_to_abbrev(team)
            if not abbrev:
                continue
            try:
                schedule = NHLScoreClient().fetch_team_schedule(abbrev, limit=1)
                if not schedule:
                    continue
                gs = schedule[0]
                nhl_home = normalize_team_name(gs.home_abbrev)
                nhl_away = normalize_team_name(gs.away_abbrev)
                nhl_pair = {nhl_home.lower(), nhl_away.lower()}
                nhl_date = gs.start_time_utc[:10] if gs.start_time_utc else ""

                # Find existing edge that matches this game by team pair
                matched_idx = None
                for i, edge in enumerate(matchup_edges):
                    edge_pair = {
                        edge.get("home_team", "").lower(),
                        edge.get("away_team", "").lower(),
                    }
                    if edge_pair == nhl_pair:
                        matched_idx = i
                        break

                logger.info(
                    "[SCHED] NHL says next game: %s @ %s on %s | matched_idx=%s",
                    nhl_away, nhl_home, nhl_date, matched_idx,
                )
                if matched_idx is not None:
                    # Edge exists — fix date to NHL value and attach game_status
                    matchup_edges[matched_idx]["game_date"] = nhl_date
                    matchup_edges[matched_idx]["game_status"] = asdict(gs)
                    # Remove OTHER NO_ODDS edges for this team — they're for
                    # later games, not the next one, and confuse the LLM.
                    matchup_edges = [
                        e for i, e in enumerate(matchup_edges)
                        if i == matched_idx
                        or e.get("recommendation") != "NO_ODDS"
                        or (
                            e.get("home_team", "").lower() != team.lower()
                            and e.get("away_team", "").lower() != team.lower()
                        )
                    ]
                else:
                    # No matching edge — remove stale NO_ODDS edges for this
                    # team and add a fresh SCHEDULE edge from the NHL API.
                    before = len(matchup_edges)
                    matchup_edges = [
                        e for e in matchup_edges
                        if not (
                            e.get("recommendation") == "NO_ODDS"
                            and (
                                e.get("home_team", "").lower() == team.lower()
                                or e.get("away_team", "").lower() == team.lower()
                            )
                        )
                    ]
                    logger.info(
                        "[SCHED] removed %d stale NO_ODDS edges, adding SCHEDULE",
                        before - len(matchup_edges),
                    )
                    matchup_edges.append({
                        "home_team": nhl_home,
                        "away_team": nhl_away,
                        "home_fair_prob": 0.0,
                        "away_fair_prob": 0.0,
                        "kalshi_home_prob": None,
                        "kalshi_away_prob": None,
                        "home_edge": None,
                        "away_edge": None,
                        "recommendation": "SCHEDULE",
                        "game_date": nhl_date,
                        "game_status": asdict(gs),
                    })
            except Exception as exc:
                logger.warning("Schedule fetch failed for %s: %s", team, exc)

    # Tavily gating: search if any BET recommendation or explanation intent
    has_bet = any(e.get("recommendation") == "BET" for e in matchup_edges)
    query_lower = query.lower()
    has_keywords = any(kw in query_lower for kw in _EXPLANATION_KEYWORDS)
    should_search = has_bet or intent == "explanation" or has_keywords

    # Log final edges for mentioned teams
    if teams:
        team_edges = [
            (e.get("away_team"), e.get("home_team"), e.get("recommendation"), e.get("game_date"))
            for e in matchup_edges
            if any(t.lower() in (e.get("home_team", "").lower(), e.get("away_team", "").lower()) for t in teams)
        ]
        logger.info("[SCHED] FINAL edges for %s: %s", teams, team_edges)

    result: dict[str, Any] = {
        "matchup_edges": matchup_edges,
        "should_search_news": should_search,
        "errors": errors,
    }
    # Propagate fallback-extracted teams so generate_response can use them
    if teams != list(state.get("teams_mentioned", [])):
        result["teams_mentioned"] = teams
    return result


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

    # Filter edges to mentioned teams (regardless of intent classification)
    teams = state.get("teams_mentioned", [])
    logger.info(
        "[GEN] intent=%s teams=%s edges=%s",
        intent, teams,
        [(e.get("away_team"), e.get("home_team"), e.get("recommendation")) for e in matchup_edges],
    )
    display_edges = matchup_edges
    if teams:
        teams_lower = {t.lower() for t in teams}
        display_edges = [
            e for e in matchup_edges
            if e.get("home_team", "").lower() in teams_lower
            or e.get("away_team", "").lower() in teams_lower
        ]
        if not display_edges:
            errors = list(errors)
            errors.append(
                f"No active market found for {' vs '.join(teams)}. "
                "No active market found — the game may not be on the upcoming schedule."
            )

    # Build shared context for the LLM
    context = _build_llm_context(
        retrieved_texts, display_edges, tavily_results, errors
    )

    rationales: dict[str, str] = {}
    freeform_text = ""

    # Schedule-only queries (e.g. "When is CBJ's next game?") use the NHL
    # API data deterministically — skip the LLM to avoid hallucination.
    schedule_only = teams and display_edges and all(
        e.get("recommendation") == "SCHEDULE" for e in display_edges
    )
    logger.info(
        "[GEN] schedule_only=%s display_edges=%s",
        schedule_only,
        [(e.get("away_team"), e.get("home_team"), e.get("recommendation")) for e in display_edges],
    )

    # Determine response path:
    # - schedule-only: deterministic, no LLM call
    # - slate/matchup intents: deterministic game blocks (BET only)
    # - explanation/general intents: freeform LLM text with game header
    if schedule_only:
        pass  # deterministic — no LLM needed
    elif intent in ("explanation", "general"):
        freeform_text = _fetch_freeform(query, context)
    elif intent in ("slate", "matchup"):
        # Build focused context with only relevant edges for rationale generation
        bet_relevant = [
            e for e in display_edges
            if e.get("recommendation") == "BET"
            or (teams and e.get("recommendation") == "PASS")
        ]
        rationale_context = _build_llm_context(
            retrieved_texts, bet_relevant, tavily_results, errors
        )
        rationales = _fetch_rationales(
            query, rationale_context, display_edges, include_pass=bool(teams),
        )

    # Assemble response deterministically
    # Force "matchup" intent for schedule-only so the structured path fires
    answer = build_structured_response(
        intent="matchup" if schedule_only else intent,
        edges=display_edges,
        rationales=rationales,
        retrieved_docs=retrieved_docs,
        tavily_results=tavily_results,
        errors=errors,
        freeform_text=freeform_text,
        teams_mentioned=teams if teams else None,
        ev_only=state.get("ev_only", False),
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


def _fetch_single_rationale(
    client: OpenAI, game_key: str, context: str,
) -> str:
    """Fetch rationale bullets for a single game."""
    prompt = (
        f"{context}\n\n"
        f"Provide rationale for this game: {game_key}"
    )
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": RATIONALE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=500,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content.strip()
    parsed = json.loads(raw)
    raw_rationales = parsed.get("rationales", {})
    # Take the first (only) value regardless of key
    for v in raw_rationales.values():
        if isinstance(v, list):
            return "\n".join(f"- {b}" for b in v)
        return v
    return ""


def _fetch_rationales(
    query: str, context: str, edges: list[dict], include_pass: bool = False,
) -> dict[str, str]:
    """Ask LLM for rationale text per game, one call per game for reliability."""
    game_keys = [
        f"{e['away_team']} @ {e['home_team']}"
        for e in edges
        if e.get("recommendation") == "BET"
        or (include_pass and e.get("recommendation") == "PASS")
    ]
    if not game_keys:
        return {}

    client = _get_llm()
    full_context = f"User query: {query}\n\n{context}"
    result: dict[str, str] = {}
    for gk in game_keys:
        try:
            result[gk] = _fetch_single_rationale(client, gk, full_context)
        except Exception as exc:
            logger.warning("Rationale failed for %s: %s", gk, exc)
            result[gk] = ""
    return result


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
