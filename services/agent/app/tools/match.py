"""Matchup builder — match Odds API games to Kalshi markets and compute edges."""

from __future__ import annotations

from app.settings import settings
from app.tools.models import GameOdds, KalshiMarket, MatchupEdge
from app.tools.odds_math import compute_edge
from app.utils.team_names import normalize_team_name


def build_matchup_edges(
    odds: list[GameOdds],
    markets: list[KalshiMarket],
) -> list[MatchupEdge]:
    """Match Odds API games to Kalshi markets by team name and compute edges.

    For each game from the odds aggregator, look for corresponding Kalshi
    markets for both teams. Compute edge = fair_prob - kalshi_prob for each side.
    """
    # Index Kalshi markets by (normalized_team, game_date) to handle
    # multiple markets for the same team on different dates
    kalshi_by_team_date: dict[tuple[str, str], KalshiMarket] = {}
    for m in markets:
        key = (normalize_team_name(m.team), m.game_date)
        kalshi_by_team_date[key] = m

    results: list[MatchupEdge] = []
    for game in odds:
        # Extract date from Odds API commence_time (ISO format -> YYYY-MM-DD)
        game_date = game.commence_time[:10] if game.commence_time else ""
        home_key = (normalize_team_name(game.home_team), game_date)
        away_key = (normalize_team_name(game.away_team), game_date)

        home_market = kalshi_by_team_date.get(home_key)
        away_market = kalshi_by_team_date.get(away_key)

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

    return results


def _has_positive_edge(edge: float | None) -> bool:
    """Check if edge meets the configured threshold."""
    if edge is None:
        return False
    return edge >= settings.EDGE_THRESHOLD
