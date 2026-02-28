"""Kalshi client — fetch NHL game markets and return implied probabilities."""

from __future__ import annotations

import httpx

from app.settings import settings
from app.tools.models import KalshiMarket
from app.utils.team_names import kalshi_abbrev_to_team

# NHL game moneyline series ticker
_SERIES_TICKER = "KXNHLGAME"


class KalshiClient:
    """Fetch open NHL game markets from Kalshi."""

    def __init__(self) -> None:
        self._base_url = settings.KALSHI_API_BASE_URL

    def fetch_nhl_markets(self) -> list[KalshiMarket]:
        """Fetch open KXNHLGAME markets and return parsed KalshiMarket list.

        Ticker format: KXNHLGAME-{datecode}{away}{home}-{team_abbrev}
        e.g. KXNHLGAME-26MAR02CARSEA-SEA
        """
        markets: list[KalshiMarket] = []
        cursor: str | None = None

        while True:
            params: dict = {
                "series_ticker": _SERIES_TICKER,
                "status": "open",
                "limit": 100,
            }
            if cursor:
                params["cursor"] = cursor

            resp = httpx.get(
                f"{self._base_url}/markets",
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for m in data.get("markets", []):
                parsed = _parse_market(m)
                if parsed:
                    markets.append(parsed)

            cursor = data.get("cursor")
            if not cursor or not data.get("markets"):
                break

        return markets


def _parse_market(m: dict) -> KalshiMarket | None:
    """Parse a Kalshi market dict into a KalshiMarket.

    Extracts team abbreviation from the ticker suffix and resolves
    the opponent from the event code in the ticker.
    """
    ticker = m.get("ticker", "")
    parts = ticker.split("-")
    if len(parts) < 3:
        return None

    # Last part is the team abbreviation for this market
    team_abbrev = parts[-1]
    team = kalshi_abbrev_to_team(team_abbrev)
    if not team:
        return None

    # Middle part contains date code + both team abbrevs (e.g. "26MAR02CARSEA")
    event_code = parts[1]
    opponent = _extract_opponent(event_code, team_abbrev)

    # Extract game date from event code (e.g. "26MAR02" -> "2026-03-02")
    game_date = _parse_event_date(event_code)

    # Kalshi prices are in cents (0-100) -> convert to 0-1
    yes_ask = m.get("yes_ask", 0) / 100.0
    yes_bid = m.get("yes_bid", 0) / 100.0

    return KalshiMarket(
        ticker=ticker,
        team=team,
        yes_ask=yes_ask,
        yes_bid=yes_bid,
        opponent=opponent or "",
        game_date=game_date,
    )


def _extract_opponent(event_code: str, team_abbrev: str) -> str | None:
    """Extract the opponent team from the event code.

    Event code format: {datepart}{away_abbrev}{home_abbrev}
    e.g. "26MAR02CARSEA" -> if team is CAR, opponent is SEA and vice versa.
    """
    # Strip the date prefix (digits + month + digits) to get team abbrevs
    # Find where the alpha-alpha team codes start after the date
    upper = event_code.upper()
    team_upper = team_abbrev.upper()

    # The team codes are appended after the date portion
    # Try to find our team abbreviation and extract the other
    idx = upper.rfind(team_upper)
    if idx < 0:
        return None

    # Remove our team from the team portion to find opponent
    teams_part = upper[idx - len(upper):]  # everything from match onward
    # Actually, let's find the teams section more carefully
    # Date format is like "26MAR02" — 2 digit year + 3 char month + 2 digit day = 7 chars
    if len(event_code) < 7:
        return None

    teams_section = event_code[7:].upper()
    # teams_section is e.g. "CARSEA" — two team abbrevs concatenated
    # Find and remove our team to get the opponent
    if teams_section.startswith(team_upper):
        opp_abbrev = teams_section[len(team_upper):]
    elif teams_section.endswith(team_upper):
        opp_abbrev = teams_section[: -len(team_upper)]
    else:
        return None

    return kalshi_abbrev_to_team(opp_abbrev)


def _parse_event_date(event_code: str) -> str:
    """Parse date from event code like '26MAR02' -> '2026-03-02'."""
    if len(event_code) < 7:
        return ""

    year_2d = event_code[:2]
    month_str = event_code[2:5].upper()
    day_2d = event_code[5:7]

    months = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
        "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
        "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
    }
    month = months.get(month_str, "00")
    return f"20{year_2d}-{month}-{day_2d}"
