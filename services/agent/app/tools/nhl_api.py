"""NHL Score API client — fetch live scores and game status."""

from __future__ import annotations

import logging

import httpx

from app.tools.models import GameScore

logger = logging.getLogger(__name__)

_NHL_SCORE_URL = "https://api-web.nhle.com/v1/score/now"


class NHLScoreClient:
    """Fetch current NHL game scores and statuses from the public NHL API."""

    def fetch_live_scores(self) -> list[GameScore]:
        """Fetch today's games with state, clock, and scores."""
        resp = httpx.get(_NHL_SCORE_URL, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

        results: list[GameScore] = []
        for game in data.get("games", []):
            state = game.get("gameState", "FUT")
            period_desc = game.get("periodDescriptor", {})
            clock = game.get("clock", {})
            away = game.get("awayTeam", {})
            home = game.get("homeTeam", {})

            results.append(
                GameScore(
                    home_abbrev=home.get("abbrev", ""),
                    away_abbrev=away.get("abbrev", ""),
                    game_state=state,
                    start_time_utc=game.get("startTimeUTC", ""),
                    period=period_desc.get("number"),
                    period_type=period_desc.get("periodType", "REG"),
                    clock=clock.get("timeRemaining", ""),
                    home_score=home.get("score"),
                    away_score=away.get("score"),
                )
            )

        return results
