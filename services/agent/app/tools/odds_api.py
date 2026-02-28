"""Odds API client — fetch NHL moneyline odds and compute fair probabilities."""

from __future__ import annotations

import httpx

from app.settings import settings
from app.tools.models import GameOdds
from app.tools.odds_math import american_to_implied, devig_multiplicative
from app.utils.team_names import normalize_team_name


class OddsAPIClient:
    """Fetch NHL moneyline odds from the-odds-api and return de-vigged fair probs."""

    def __init__(self) -> None:
        if not settings.ODDS_API_KEY:
            raise ValueError("ODDS_API_KEY is required")
        self._base_url = settings.ODDS_API_BASE_URL

    def fetch_nhl_odds(self) -> list[GameOdds]:
        """Fetch current NHL moneyline odds, average across bookmakers, and de-vig."""
        resp = httpx.get(
            f"{self._base_url}/sports/icehockey_nhl/odds",
            params={
                "apiKey": settings.ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
            },
            timeout=15,
        )
        resp.raise_for_status()

        results: list[GameOdds] = []
        for game in resp.json():
            home = normalize_team_name(game["home_team"])
            away = normalize_team_name(game["away_team"])

            # Collect American odds from all bookmakers
            home_odds_list: list[int] = []
            away_odds_list: list[int] = []
            for bookmaker in game.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market["key"] != "h2h":
                        continue
                    outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                    if game["home_team"] in outcomes and game["away_team"] in outcomes:
                        home_odds_list.append(outcomes[game["home_team"]])
                        away_odds_list.append(outcomes[game["away_team"]])

            if not home_odds_list:
                continue

            # Average American odds across bookmakers
            avg_home_odds = round(sum(home_odds_list) / len(home_odds_list))
            avg_away_odds = round(sum(away_odds_list) / len(away_odds_list))

            # Convert to implied probabilities and de-vig
            home_implied = american_to_implied(avg_home_odds)
            away_implied = american_to_implied(avg_away_odds)
            home_fair, away_fair = devig_multiplicative([home_implied, away_implied])

            results.append(
                GameOdds(
                    home_team=home,
                    away_team=away,
                    home_fair_prob=round(home_fair, 4),
                    away_fair_prob=round(away_fair, 4),
                    commence_time=game.get("commence_time", ""),
                    bookmakers_used=len(home_odds_list),
                )
            )

        return results
