"""Deterministic response formatter enforcing AGENTS.md §8 schema."""

from __future__ import annotations


def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt_edge(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:+.1f}%"


def _best_side(edge: dict) -> dict:
    """Pick the side with the better edge for display."""
    home_e = edge.get("home_edge")
    away_e = edge.get("away_edge")
    home_val = home_e if home_e is not None else float("-inf")
    away_val = away_e if away_e is not None else float("-inf")

    if away_val > home_val:
        return {
            "team": edge["away_team"],
            "fair_prob": edge.get("away_fair_prob"),
            "kalshi_prob": edge.get("kalshi_away_prob"),
            "edge": away_e,
        }
    return {
        "team": edge["home_team"],
        "fair_prob": edge.get("home_fair_prob"),
        "kalshi_prob": edge.get("kalshi_home_prob"),
        "edge": home_e,
    }


def build_game_block(edge: dict, rationale: str) -> str:
    """Build one §8 game block deterministically from edge data."""
    best = _best_side(edge)
    home = edge["home_team"]
    away = edge["away_team"]

    return (
        f"Recommendation: {edge['recommendation']}\n"
        f"Game: {away} @ {home}\n"
        f"Kalshi Probability: {_fmt_pct(best['kalshi_prob'])} ({best['team']})\n"
        f"Fair Probability (de-vigged): {_fmt_pct(best['fair_prob'])} ({best['team']})\n"
        f"Edge: {_fmt_edge(best['edge'])}\n"
        f"Rationale: {rationale}"
    )


def build_citations_block(
    retrieved_docs: list[dict],
    has_odds: bool,
    tavily_results: list[dict],
) -> str:
    """Build the Citations section from structured data."""
    lines: list[str] = ["Citations:"]

    for doc in retrieved_docs:
        meta = doc.get("metadata", {})
        teams_list = meta.get("teams")
        if teams_list and isinstance(teams_list, list) and len(teams_list) >= 2:
            label = f"{teams_list[0]} vs {teams_list[1]}"
        else:
            label = meta.get("team", "Unknown")
        doc_id = doc.get("id", "")
        season = meta.get("season_id", "")
        doc_type = meta.get("doc_type", "")
        lines.append(f"- [{doc_id}] {label} ({season}, {doc_type}) [Qdrant]")

    if has_odds:
        lines.append("- Odds API (de-vigged moneyline)")

    for r in tavily_results:
        title = r.get("title", "")
        url = r.get("url", "")
        lines.append(f"- {title} ({url})")

    return "\n".join(lines)


def build_structured_response(
    intent: str,
    edges: list[dict],
    rationales: dict[str, str],
    retrieved_docs: list[dict],
    tavily_results: list[dict],
    errors: list[str],
    freeform_text: str = "",
) -> str:
    """Assemble the full response with deterministic §8 formatting.

    For slate/matchup intents: game blocks are built from edge data,
    only rationale text comes from LLM.
    For explanation/general intents: freeform LLM text is used, with
    citations and disclaimer appended.
    """
    parts: list[str] = []

    if intent in ("slate", "matchup"):
        no_market: list[str] = []
        for e in edges:
            if e["recommendation"] == "NO_MARKET":
                no_market.append(f"{e['away_team']} @ {e['home_team']}")
                continue
            game_key = f"{e['away_team']} @ {e['home_team']}"
            rationale = rationales.get(game_key, "No analysis available.")
            parts.append(build_game_block(e, rationale))

        if no_market:
            parts.append(
                f"{len(no_market)} other game(s) have no Kalshi market "
                f"available: {', '.join(no_market)}"
            )
    else:
        # explanation / general — use freeform LLM text
        if freeform_text:
            parts.append(freeform_text)

    if errors:
        parts.append("Note: " + "; ".join(errors))

    citations_block = build_citations_block(
        retrieved_docs, bool(edges), tavily_results
    )
    parts.append(citations_block)
    parts.append("Disclaimer: Not financial advice.")

    return "\n\n".join(parts)
