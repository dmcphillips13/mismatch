"""Deterministic response formatter for structured game block output."""

from __future__ import annotations

from datetime import datetime

from zoneinfo import ZoneInfo


def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt_edge(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:+.1f}%"


def _ev_team(edge: dict) -> tuple[str, str]:
    """Return (ev_team, other_team) for the side with the better edge."""
    home_e = edge.get("home_edge")
    away_e = edge.get("away_edge")
    home_val = home_e if home_e is not None else float("-inf")
    away_val = away_e if away_e is not None else float("-inf")
    if away_val > home_val:
        return edge["away_team"], edge["home_team"]
    return edge["home_team"], edge["away_team"]


_PERIOD_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}
_ET = ZoneInfo("America/New_York")


def _format_game_status(edge: dict) -> str:
    """Return a display string for game timing/status, or empty string if unavailable."""
    gs = edge.get("game_status")
    if not gs:
        return ""

    state = gs.get("game_state", "")
    away_score = gs.get("away_score")
    home_score = gs.get("home_score")

    if state in ("FUT", "PRE"):
        raw = gs.get("start_time_utc", "")
        if raw:
            try:
                utc_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                et_dt = utc_dt.astimezone(_ET)
                return et_dt.strftime("%-I:%M %p ET")
            except (ValueError, OSError):
                pass
        return ""

    if state in ("LIVE", "CRIT"):
        period = gs.get("period")
        period_type = gs.get("period_type", "REG")
        clock = gs.get("clock", "")

        if period_type == "OT":
            period_str = "OT"
        elif period_type == "SO":
            period_str = "SO"
        else:
            period_str = _PERIOD_ORDINALS.get(period, f"P{period}") if period else ""

        score_str = ""
        if away_score is not None and home_score is not None:
            away_abbrev = gs.get("away_abbrev", "")
            home_abbrev = gs.get("home_abbrev", "")
            score_str = f" {away_abbrev} {away_score}, {home_abbrev} {home_score}"

        parts = ["LIVE"]
        if period_str and clock:
            parts.append(f"{period_str}, {clock} remaining")
        elif period_str:
            parts.append(period_str)
        result = " — ".join(parts)
        if score_str:
            result += f" |{score_str}"
        return result

    if state in ("OFF", "FINAL"):
        period_type = gs.get("period_type", "REG")
        score_str = ""
        if away_score is not None and home_score is not None:
            away_abbrev = gs.get("away_abbrev", "")
            home_abbrev = gs.get("home_abbrev", "")
            score_str = f" {away_abbrev} {away_score}, {home_abbrev} {home_score}"

        if period_type == "OT":
            return f"Final (OT){' |' + score_str if score_str else ''}"
        if period_type == "SO":
            return f"Final (SO){' |' + score_str if score_str else ''}"
        return f"Final{' |' + score_str if score_str else ''}"

    return ""


def _format_schedule_line(edge: dict) -> str:
    """Format a SCHEDULE edge as a clean 'next game' sentence."""
    home = edge["home_team"]
    away = edge["away_team"]
    matchup = f"**{away} @ {home}**"

    # Format date and time from game_status
    gs = edge.get("game_status", {})
    raw = gs.get("start_time_utc", "") or edge.get("game_date", "")
    date_str = ""
    time_str = ""
    if raw:
        try:
            utc_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            et_dt = utc_dt.astimezone(_ET)
            date_str = et_dt.strftime("%B %-d")
            time_str = et_dt.strftime("%-I:%M %p ET")
        except (ValueError, OSError):
            date_str = edge.get("game_date", "")

    if date_str and time_str:
        return f"The next game is {matchup} on {date_str} at {time_str}."
    if date_str:
        return f"The next game is {matchup} on {date_str}."
    return f"The next game is {matchup}."


def _build_game_header(edge: dict) -> str:
    """Build the headline + both-sides odds table for a game (no rationale)."""
    home = edge["home_team"]
    away = edge["away_team"]
    rec = edge.get("recommendation", "")

    if rec == "BET":
        best, other = _ev_team(edge)
        title = f"### {best} over {other}"
    else:
        title = f"### {away} @ {home}"

    status = _format_game_status(edge)
    subtitle = f"*{away} @ {home} — {status}*" if status else f"*{away} @ {home}*"

    # Schedule-only games — no odds data, just game info with start time
    if rec == "SCHEDULE":
        return f"{title}\n{subtitle}"

    # Kalshi-only games (no Odds API data) — show simplified table
    if rec == "NO_ODDS":
        kalshi_away = edge.get("kalshi_away_prob")
        kalshi_home = edge.get("kalshi_home_prob")
        rows = "\n".join(
            f"| {t} | {_fmt_pct(k)} |"
            for t, k in [(away, kalshi_away), (home, kalshi_home)]
            if k is not None
        )
        return (
            f"{title}\n"
            f"{subtitle}\n\n"
            f"| Team | Kalshi |\n"
            f"|---|---|\n"
            f"{rows}"
        )

    sides = [
        (away, edge.get("kalshi_away_prob"), edge.get("away_fair_prob"), edge.get("away_edge")),
        (home, edge.get("kalshi_home_prob"), edge.get("home_fair_prob"), edge.get("home_edge")),
    ]
    sides.sort(key=lambda s: s[3] if s[3] is not None else float("-inf"), reverse=True)

    rows = "\n".join(
        f"| {t} | {_fmt_pct(k)} | {_fmt_pct(f)} | {_fmt_edge(e)} |"
        for t, k, f, e in sides
    )

    return (
        f"{title}\n"
        f"{subtitle}\n\n"
        f"| Team | Kalshi | Fair (de-vigged) | Edge |\n"
        f"|---|---|---|---|\n"
        f"{rows}"
    )


def build_game_block(edge: dict, rationale: str) -> str:
    """Build one game block in markdown from edge data."""
    return f"{_build_game_header(edge)}\n\n{rationale}"


def build_citations_block(
    retrieved_docs: list[dict],
    has_odds: bool,
    tavily_results: list[dict],
) -> str:
    """Build the Citations section from structured data."""
    lines: list[str] = ["#### Sources"]

    for doc in retrieved_docs:
        meta = doc.get("metadata", {})
        teams_list = meta.get("teams")
        if teams_list and isinstance(teams_list, list) and len(teams_list) >= 2:
            label = f"{teams_list[0]} vs {teams_list[1]}"
        else:
            label = meta.get("team", "Unknown")
        season = meta.get("season_id", "")
        doc_type = meta.get("doc_type", "")
        lines.append(f"- {label} ({season}, {doc_type})")

    if has_odds:
        lines.append("- Odds API (de-vigged moneyline)")

    for r in tavily_results:
        title = r.get("title", "")
        url = r.get("url", "")
        if url:
            lines.append(f"- [{title}]({url})")
        else:
            lines.append(f"- {title}")

    return "\n".join(lines)


def _build_intro(bet_count: int, total_count: int, teams: list[str] | None = None) -> str:
    """Build a conversational intro sentence."""
    team_str = " and ".join(teams) if teams else None

    if total_count == 0:
        if team_str:
            return f"I didn't find any upcoming games for the **{team_str}** right now."
        return "I didn't find any upcoming games right now."

    ev_note = ""
    if bet_count > 0:
        ev_note = f" with **{bet_count}** +EV opportunity{'s' if bet_count != 1 else ''}"

    if team_str:
        return (
            f"Here's what I found for the **{team_str}** — "
            f"**{total_count}** game{'s' if total_count != 1 else ''}{ev_note}:"
        )
    return (
        f"Here {'are' if total_count != 1 else 'is'} **{total_count}** upcoming "
        f"game{'s' if total_count != 1 else ''}{ev_note}:"
    )


def build_structured_response(
    intent: str,
    edges: list[dict],
    rationales: dict[str, str],
    retrieved_docs: list[dict],
    tavily_results: list[dict],
    errors: list[str],
    freeform_text: str = "",
    teams_mentioned: list[str] | None = None,
) -> str:
    """Assemble the full response with deterministic formatting.

    For slate/matchup intents with BET edges: game blocks with rationales.
    For freeform fallback (matchup with no BET, explanation, general):
    game header + odds table prepended before LLM commentary.
    """
    parts: list[str] = []

    # Handle SCHEDULE edges first — these are standalone "next game" results
    schedule_edges = [e for e in edges if e.get("recommendation") == "SCHEDULE"]
    non_schedule_edges = [e for e in edges if e.get("recommendation") != "SCHEDULE"]

    if freeform_text:
        # Freeform path — prepend game headers for relevant edges
        displayable = [
            e for e in non_schedule_edges
            if e.get("recommendation") not in ("NO_MARKET", "NO_ODDS")
        ]
        for e in displayable:
            parts.append(_build_game_header(e))
        # If only schedule edges and freeform, show schedule info too
        if not displayable and schedule_edges:
            for e in schedule_edges:
                parts.append(_format_schedule_line(e))
        parts.append(freeform_text)
    elif intent in ("slate", "matchup"):
        # Edges with full data (Odds API + optionally Kalshi)
        has_odds = [
            e for e in non_schedule_edges
            if e.get("recommendation") not in ("NO_MARKET", "NO_ODDS")
        ]
        # Kalshi-only edges (no Odds API data)
        no_odds = [e for e in non_schedule_edges if e.get("recommendation") == "NO_ODDS"]
        bet_edges = [e for e in has_odds if e.get("recommendation") == "BET"]

        if teams_mentioned:
            team_str = " and ".join(teams_mentioned)
            nomarket = [e for e in non_schedule_edges if e.get("recommendation") == "NO_MARKET"]

            # For Kalshi-only games, show only the nearest upcoming one
            if no_odds:
                no_odds.sort(key=lambda e: e.get("game_date", ""))
                no_odds = no_odds[:1]

            show_edges = has_odds + no_odds

            # Matchup query — show all games for mentioned teams
            if bet_edges:
                parts.append(
                    f"**Yes** — the **{team_str}** play today and I found "
                    f"a +EV opportunity:"
                )
            elif has_odds:
                parts.append(
                    f"**Yes** — the **{team_str}** play today, "
                    f"but I don't see a +EV edge right now:"
                )
            elif no_odds:
                e = no_odds[0]
                parts.append(
                    f"The **{team_str}** next game is "
                    f"**{e['away_team']} @ {e['home_team']}** "
                    f"on {e.get('game_date', '')}:"
                )
            elif schedule_edges:
                # Schedule-only fallback — show next game from NHL API
                for e in schedule_edges:
                    parts.append(_format_schedule_line(e))
            elif nomarket:
                games = [f"{e['away_team']} @ {e['home_team']}" for e in nomarket]
                parts.append(
                    f"The **{team_str}** game ({', '.join(games)}) is scheduled "
                    f"but there's no Kalshi market available for it yet, "
                    f"so I can't calculate an edge."
                )
            for e in show_edges:
                game_key = f"{e['away_team']} @ {e['home_team']}"
                rationale = rationales.get(game_key, "")
                if rationale:
                    parts.append(build_game_block(e, rationale))
                else:
                    parts.append(_build_game_header(e))
        else:
            # Slate query — show all games, highlight +EV ones
            total_with_market = len(has_odds)
            parts.append(_build_intro(len(bet_edges), total_with_market))

            for e in has_odds:
                game_key = f"{e['away_team']} @ {e['home_team']}"
                if e.get("recommendation") == "BET":
                    rationale = rationales.get(game_key, "No analysis available.")
                    parts.append(build_game_block(e, rationale))
                else:
                    parts.append(_build_game_header(e))

    if errors:
        parts.append("*Note: " + "; ".join(errors) + "*")

    parts.append("*Disclaimer: Not financial advice.*")

    return "\n\n".join(parts)
