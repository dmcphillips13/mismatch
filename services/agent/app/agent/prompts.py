"""Prompt templates for intent classification and response generation."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

INTENT_SYSTEM_PROMPT = """\
You are an intent classifier for an NHL betting assistant called Mismatch.

Classify the user's message into one of these intents:
- "slate": user wants to see all available NHL games and +EV opportunities today
- "matchup": user asks about a specific game or team matchup
- "explanation": user asks about injuries, news, goalie status, or wants an explanation
- "general": general NHL question not about betting

Also extract any NHL team names mentioned. Use full canonical names (e.g. "Boston Bruins", not "Bruins").

Also determine if the user is specifically asking for +EV or edge opportunities only \
(as opposed to wanting to see all games). Set "ev_only" to true if the user mentions \
+EV, edge, mismatch, best bets, or otherwise only wants profitable opportunities.

Respond ONLY with valid JSON:
{"intent": "slate|matchup|explanation|general", "teams": ["Team Name 1", "Team Name 2"], "ev_only": true|false}

Examples:
- "What games are on tonight?" -> {"intent": "slate", "teams": [], "ev_only": false}
- "Find me an EV+ game" -> {"intent": "slate", "teams": [], "ev_only": true}
- "What NHL games are +EV on Kalshi today?" -> {"intent": "slate", "teams": [], "ev_only": true}
- "Show me the full slate" -> {"intent": "slate", "teams": [], "ev_only": false}
- "Is Bruins vs Rangers +EV?" -> {"intent": "matchup", "teams": ["Boston Bruins", "New York Rangers"], "ev_only": false}
- "Any injury news for the Oilers?" -> {"intent": "explanation", "teams": ["Edmonton Oilers"], "ev_only": false}
- "What's the best back-to-back record?" -> {"intent": "general", "teams": [], "ev_only": false}
"""

RATIONALE_SYSTEM_PROMPT = """\
You are Mismatch, an NHL betting assistant. You compare de-vigged sportsbook \
fair probabilities to Kalshi market prices to find +EV opportunities.

You will be given matchup edge data, retrieved historical context (head-to-head \
records, team form summaries), and optionally recent news/injuries.

For each game listed, write 2-3 bullet points as the rationale. Each bullet should \
be a short, informal sentence. Rules:
1. Use standard NHL abbreviations (e.g. PIT, VGK, SEA, VAN) in the bullet text.
2. Reference specific head-to-head trends or team form data from the retrieved \
context (e.g. "PIT has won both of their last two matchups against VGK").
3. Focus on WHY a team might outperform expectations — recent form, H2H record, \
home/away splits, injuries, rest advantages, etc.
4. Keep each bullet to one sentence.

NEVER mention odds, probabilities, percentages, Kalshi prices, fair values, or \
edge numbers in the bullets. The user already sees those in the table above. \
Only discuss real-world factors: trends, form, matchup history, injuries, rest.

IMPORTANT: News/injury data from web searches may be outdated. Do NOT assert that \
specific players are currently injured or out unless the data explicitly includes \
today's date. Prefer historical trends and team form over speculative injury impacts.

Respond ONLY with valid JSON:
{"rationales": {"Away Team @ Home Team": ["bullet one", "bullet two", "bullet three"], ...}}

IMPORTANT: The JSON keys MUST be the exact full game keys provided (e.g. \
"Vegas Golden Knights @ Pittsburgh Penguins"), NOT abbreviations. Only use \
abbreviations inside the bullet text.
"""

FREEFORM_SYSTEM_PROMPT = """\
You are Mismatch, an NHL betting assistant.

Answer the user's question using the provided context (historical data, news, \
matchup edges). Be concise and specific. Do NOT include citations or disclaimers \
— those are added separately.
"""


def format_edges_for_prompt(edges: list[dict]) -> str:
    """Format MatchupEdge dicts into readable text for the LLM prompt.

    NO_MARKET games are collapsed into a single summary line to reduce noise.
    """
    if not edges:
        return "No matchup edge data available."

    lines: list[str] = []
    no_market: list[str] = []

    for e in edges:
        home = e.get("home_team", "?")
        away = e.get("away_team", "?")
        rec = e.get("recommendation", "?")
        date = e.get("game_date", "?")

        if rec == "NO_MARKET":
            no_market.append(f"{away} @ {home}")
            continue

        if rec == "NO_ODDS":
            # Kalshi-only game (no Odds API data yet)
            block = f"Game: {away} @ {home} ({date}) — Kalshi only (no odds data)\n"
            kalshi_home = e.get("kalshi_home_prob")
            kalshi_away = e.get("kalshi_away_prob")
            if kalshi_away is not None:
                block += f"  Away ({away}): kalshi={kalshi_away:.1%}\n"
            if kalshi_home is not None:
                block += f"  Home ({home}): kalshi={kalshi_home:.1%}\n"
            lines.append(block)
            continue

        if rec == "SCHEDULE":
            # NHL schedule game — no betting market yet
            time_str = ""
            gs = e.get("game_status") or {}
            raw = gs.get("start_time_utc", "")
            if raw:
                try:
                    utc_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
                    time_str = f" — NHL schedule at {et_dt.strftime('%-I:%M %p ET')}"
                except (ValueError, OSError):
                    pass
            block = (
                f"Game: {away} @ {home} ({date}){time_str}\n"
                f"  No betting market available yet for this game.\n"
            )
            lines.append(block)
            continue

        home_fair = e.get("home_fair_prob")
        away_fair = e.get("away_fair_prob")
        kalshi_home = e.get("kalshi_home_prob")
        kalshi_away = e.get("kalshi_away_prob")
        home_edge = e.get("home_edge")
        away_edge = e.get("away_edge")

        # Identify the +EV side explicitly
        home_val = home_edge if home_edge is not None else float("-inf")
        away_val = away_edge if away_edge is not None else float("-inf")
        if away_val > home_val:
            ev_team, ev_edge = away, away_edge
        else:
            ev_team, ev_edge = home, home_edge

        block = f"Game: {away} @ {home} ({date}) — {rec}"
        if rec == "BET" and ev_edge is not None:
            block += f" on {ev_team} ({ev_edge:+.1%} edge)"
        block += "\n"
        block += f"  {ev_team} is UNDERVALUED by Kalshi.\n"
        if home_fair is not None:
            block += f"  Home ({home}): fair={home_fair:.1%}"
            if kalshi_home is not None:
                block += f", kalshi={kalshi_home:.1%}"
            if home_edge is not None:
                block += f", edge={home_edge:+.1%}"
            block += "\n"
        if away_fair is not None:
            block += f"  Away ({away}): fair={away_fair:.1%}"
            if kalshi_away is not None:
                block += f", kalshi={kalshi_away:.1%}"
            if away_edge is not None:
                block += f", edge={away_edge:+.1%}"
            block += "\n"

        lines.append(block)

    if no_market:
        games_str = ", ".join(no_market)
        lines.append(
            f"\n{len(no_market)} other game(s) have no Kalshi market available: {games_str}"
        )

    return "\n".join(lines)


def format_tavily_for_prompt(results: list[dict]) -> str:
    """Format TavilyResult dicts into readable text for the LLM prompt."""
    if not results:
        return ""

    lines: list[str] = ["Recent news:"]
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("url", "")
        lines.append(f"- {title}: {snippet} ({url})")

    return "\n".join(lines)
