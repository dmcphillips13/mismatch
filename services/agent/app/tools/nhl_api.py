"""NHL Score API client — fetch live scores and game status."""

from __future__ import annotations

import logging

import httpx

from app.tools.models import GameScore

logger = logging.getLogger(__name__)

_NHL_SCORE_URL = "https://api-web.nhle.com/v1/score/now"
_NHL_SCHEDULE_URL = "https://api-web.nhle.com/v1/club-schedule-season/{abbrev}/now"


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

    def fetch_team_schedule(self, abbrev: str, limit: int = 3) -> list[GameScore]:
        """Fetch next upcoming games for a team from the NHL season schedule.

        Calls /v1/club-schedule-season/{abbrev}/now, filters to future games
        (gameState == "FUT"), and returns the next ``limit`` games.
        """
        url = _NHL_SCHEDULE_URL.format(abbrev=abbrev)
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("NHL schedule fetch failed for %s: %s", abbrev, exc)
            return []

        data = resp.json()

        future_games = [
            g for g in data.get("games", [])
            if g.get("gameState") == "FUT"
        ]
        # Already chronological from the API, but sort to be safe
        future_games.sort(key=lambda g: g.get("gameDate", ""))

        results: list[GameScore] = []
        for game in future_games[:limit]:
            away = game.get("awayTeam", {})
            home = game.get("homeTeam", {})
            results.append(
                GameScore(
                    home_abbrev=home.get("abbrev", ""),
                    away_abbrev=away.get("abbrev", ""),
                    game_state=game.get("gameState", "FUT"),
                    start_time_utc=game.get("startTimeUTC", ""),
                    period=None,
                    period_type="REG",
                    clock="",
                    home_score=None,
                    away_score=None,
                )
            )

        return results
