"""Matchup builder — match Odds API games to Kalshi markets and compute edges."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.settings import settings
from app.tools.models import GameOdds, KalshiMarket, MatchupEdge
from app.tools.odds_math import compute_edge
from app.utils.team_names import normalize_team_name

# US Eastern offset (UTC-5 standard, UTC-4 DST). Using -4 is safer for
# sports scheduling since games happen in the evening during DST months.
_ET_OFFSET = timezone(timedelta(hours=-4))


def _commence_to_local_date(commence_time: str) -> str:
    """Convert Odds API UTC commence_time to US Eastern date string.

    The Odds API returns times in UTC, so a 10:10 PM ET game shows as
    2026-03-01T02:10:00Z. Kalshi lists that game as 2026-02-28.
    Converting to Eastern time fixes the date mismatch.
    """
    try:
        dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        return dt.astimezone(_ET_OFFSET).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        # Fallback: just take the first 10 chars
        return commence_time[:10] if commence_time else ""


def build_matchup_edges(
    odds: list[GameOdds],
    markets: list[KalshiMarket],
) -> list[MatchupEdge]:
    """Match Odds API games to Kalshi markets by team name and compute edges.

    For each game from the odds aggregator, look for corresponding Kalshi
    markets for both teams. Compute edge = fair_prob - kalshi_prob for each side.
    """
    # Index Kalshi markets by (normalized_team, game_date)
    kalshi_by_team_date: dict[tuple[str, str], KalshiMarket] = {}
    for m in markets:
        norm = normalize_team_name(m.team)
        kalshi_by_team_date[(norm, m.game_date)] = m

    results: list[MatchupEdge] = []
    matched_kalshi_keys: set[tuple[str, str]] = set()

    for game in odds:
        # Convert UTC commence_time to US Eastern date to match Kalshi dates
        game_date = _commence_to_local_date(game.commence_time)
        home_norm = normalize_team_name(game.home_team)
        away_norm = normalize_team_name(game.away_team)

        home_market = kalshi_by_team_date.get((home_norm, game_date))
        away_market = kalshi_by_team_date.get((away_norm, game_date))

        if home_market:
            matched_kalshi_keys.add((home_norm, game_date))
        if away_market:
            matched_kalshi_keys.add((away_norm, game_date))

        # Use yes_ask as the Kalshi implied probability (what you'd pay to buy)
        kalshi_home = home_market.yes_ask if home_market else None
        kalshi_away = away_market.yes_ask if away_market else None

        home_edge = (
            compute_edge(game.home_fair_prob, kalshi_home)
            if kalshi_home is not None
            else None
        )
        away_edge = (
            compute_edge(game.away_fair_prob, kalshi_away)
            if kalshi_away is not None
            else None
        )

        # Determine recommendation
        if kalshi_home is None and kalshi_away is None:
            recommendation = "NO_MARKET"
        elif _has_positive_edge(home_edge) or _has_positive_edge(away_edge):
            recommendation = "BET"
        else:
            recommendation = "PASS"

        # Prefer Kalshi's game_date (canonical), fall back to commence_time
        display_date = ""
        if home_market:
            display_date = home_market.game_date
        elif away_market:
            display_date = away_market.game_date
        else:
            display_date = game_date

        results.append(
            MatchupEdge(
                home_team=game.home_team,
                away_team=game.away_team,
                home_fair_prob=game.home_fair_prob,
                away_fair_prob=game.away_fair_prob,
                kalshi_home_prob=kalshi_home,
                kalshi_away_prob=kalshi_away,
                home_edge=round(home_edge, 4) if home_edge is not None else None,
                away_edge=round(away_edge, 4) if away_edge is not None else None,
                recommendation=recommendation,
                game_date=display_date,
            )
        )

    # Add Kalshi-only games (markets with no corresponding Odds API game).
    # Only include the NEXT upcoming game per team pair — avoids showing
    # multiple future games that simply haven't entered the Odds API window.
    unmatched: dict[tuple[str, str], list[KalshiMarket]] = {}
    for m in markets:
        norm = normalize_team_name(m.team)
        if (norm, m.game_date) not in matched_kalshi_keys:
            opp_norm = normalize_team_name(m.opponent)
            # Use sorted pair as key so both sides group together
            pair_key = (min(norm, opp_norm), max(norm, opp_norm))
            game_key = (pair_key[0] + "|" + pair_key[1], m.game_date)
            unmatched.setdefault(game_key, []).append(m)

    # Keep only the earliest date per team pair
    earliest_per_pair: dict[str, tuple[str, list[KalshiMarket]]] = {}
    for (pair_str, game_date), pair_markets in unmatched.items():
        if pair_str not in earliest_per_pair or game_date < earliest_per_pair[pair_str][0]:
            earliest_per_pair[pair_str] = (game_date, pair_markets)

    for pair_str, (game_date, pair_markets) in earliest_per_pair.items():
        if len(pair_markets) == 2:
            # Both sides available — pair them
            home_m = next(
                (m for m in pair_markets
                 if normalize_team_name(m.team) == normalize_team_name(
                     next(om for om in pair_markets if om is not m).opponent
                 )),
                pair_markets[0],
            )
            away_m = next(m for m in pair_markets if m is not home_m)
            home_team = normalize_team_name(home_m.team)
            away_team = normalize_team_name(away_m.team)
            kalshi_home = home_m.yes_ask
            kalshi_away = away_m.yes_ask
        else:
            m = pair_markets[0]
            home_team = normalize_team_name(m.opponent)
            away_team = normalize_team_name(m.team)
            kalshi_home = None
            kalshi_away = m.yes_ask

        results.append(
            MatchupEdge(
                home_team=home_team,
                away_team=away_team,
                home_fair_prob=0.0,
                away_fair_prob=0.0,
                kalshi_home_prob=kalshi_home,
                kalshi_away_prob=kalshi_away,
                home_edge=None,
                away_edge=None,
                recommendation="NO_ODDS",
                game_date=game_date,
            )
        )

    return results


def _has_positive_edge(edge: float | None) -> bool:
    """Check if edge meets the configured threshold."""
    if edge is None:
        return False
    return edge >= settings.EDGE_THRESHOLD
