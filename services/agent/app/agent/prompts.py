"""Prompt templates for intent classification and response generation."""

from __future__ import annotations

INTENT_SYSTEM_PROMPT = """\
You are an intent classifier for an NHL betting assistant called Mismatch.

Classify the user's message into one of these intents:
- "slate": user wants to see all available NHL games and +EV opportunities today
- "matchup": user asks about a specific game or team matchup
- "explanation": user asks about injuries, news, goalie status, or wants an explanation
- "general": general NHL question not about betting

Also extract any NHL team names mentioned. Use full canonical names (e.g. "Boston Bruins", not "Bruins").

Respond ONLY with valid JSON:
{"intent": "slate|matchup|explanation|general", "teams": ["Team Name 1", "Team Name 2"]}

Examples:
- "What NHL games are +EV on Kalshi today?" -> {"intent": "slate", "teams": []}
- "Is Bruins vs Rangers +EV?" -> {"intent": "matchup", "teams": ["Boston Bruins", "New York Rangers"]}
- "Any injury news for the Oilers?" -> {"intent": "explanation", "teams": ["Edmonton Oilers"]}
- "What's the best back-to-back record?" -> {"intent": "general", "teams": []}
"""

RATIONALE_SYSTEM_PROMPT = """\
You are Mismatch, an NHL betting assistant. You compare de-vigged sportsbook \
fair probabilities to Kalshi market prices to find +EV opportunities.

You will be given matchup edge data, historical context, and optionally recent news. \
For each game listed, provide a brief rationale (1-2 sentences) explaining the \
recommendation. Consider team form, historical matchups, injuries/news, and the edge.

Respond ONLY with valid JSON:
{"rationales": {"Away Team @ Home Team": "rationale text", ...}}

Use the exact game keys provided. Do not add extra keys.
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

        home_fair = e.get("home_fair_prob")
        away_fair = e.get("away_fair_prob")
        kalshi_home = e.get("kalshi_home_prob")
        kalshi_away = e.get("kalshi_away_prob")
        home_edge = e.get("home_edge")
        away_edge = e.get("away_edge")

        block = f"Game: {away} @ {home} ({date}) — {rec}\n"
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
