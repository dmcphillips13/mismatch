"""Team normalization helpers shared across pipeline, retrieval, and tools."""

from __future__ import annotations

import re


_TEAM_ALIASES: dict[str, str] = {
    "anaheim ducks": "Anaheim Ducks",
    "arizona coyotes": "Utah Mammoth",
    "boston bruins": "Boston Bruins",
    "buffalo sabres": "Buffalo Sabres",
    "calgary flames": "Calgary Flames",
    "carolina hurricanes": "Carolina Hurricanes",
    "chicago blackhawks": "Chicago Blackhawks",
    "colorado avalanche": "Colorado Avalanche",
    "columbus blue jackets": "Columbus Blue Jackets",
    "dallas stars": "Dallas Stars",
    "detroit red wings": "Detroit Red Wings",
    "edmonton oilers": "Edmonton Oilers",
    "florida panthers": "Florida Panthers",
    "los angeles kings": "Los Angeles Kings",
    "la kings": "Los Angeles Kings",
    "minnesota wild": "Minnesota Wild",
    "montreal canadiens": "Montreal Canadiens",
    "montréal canadiens": "Montreal Canadiens",
    "nashville predators": "Nashville Predators",
    "new jersey devils": "New Jersey Devils",
    "new york islanders": "New York Islanders",
    "new york rangers": "New York Rangers",
    "ottawa senators": "Ottawa Senators",
    "philadelphia flyers": "Philadelphia Flyers",
    "pittsburgh penguins": "Pittsburgh Penguins",
    "san jose sharks": "San Jose Sharks",
    "seattle kraken": "Seattle Kraken",
    "st louis blues": "St. Louis Blues",
    "st. louis blues": "St. Louis Blues",
    "tampa bay lightning": "Tampa Bay Lightning",
    "toronto maple leafs": "Toronto Maple Leafs",
    "utah hockey club": "Utah Mammoth",
    "utah mammoth": "Utah Mammoth",
    "vancouver canucks": "Vancouver Canucks",
    "vegas golden knights": "Vegas Golden Knights",
    "washington capitals": "Washington Capitals",
    "winnipeg jets": "Winnipeg Jets",
}


def normalize_team_name(name: str) -> str:
    """Normalize team names across raw CSVs, Odds API, Kalshi, and user queries."""
    cleaned = re.sub(r"\s+", " ", name.replace("&", "and")).strip().lower()
    return _TEAM_ALIASES.get(cleaned, name.strip())


def slugify_team_name(name: str) -> str:
    """Return a deterministic team slug for ids and matching."""
    return re.sub(r"[^a-z0-9]+", "-", normalize_team_name(name).lower()).strip("-")


# Kalshi ticker abbreviations → canonical team names
_KALSHI_ABBREVS: dict[str, str] = {
    "ANA": "Anaheim Ducks",
    "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres",
    "CGY": "Calgary Flames",
    "CAR": "Carolina Hurricanes",
    "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche",
    "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers",
    "LA": "Los Angeles Kings",
    "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens",
    "NSH": "Nashville Predators",
    "NJ": "New Jersey Devils",
    "NYI": "New York Islanders",
    "NYR": "New York Rangers",
    "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins",
    "SJ": "San Jose Sharks",
    "SEA": "Seattle Kraken",
    "STL": "St. Louis Blues",
    "TB": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs",
    "UTA": "Utah Mammoth",
    "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights",
    "WSH": "Washington Capitals",
    "WPG": "Winnipeg Jets",
}

# Reverse lookup: canonical name → Kalshi abbreviation
_TEAM_TO_KALSHI: dict[str, str] = {v: k for k, v in _KALSHI_ABBREVS.items()}


def kalshi_abbrev_to_team(abbrev: str) -> str | None:
    """Convert a Kalshi ticker abbreviation to canonical team name."""
    return _KALSHI_ABBREVS.get(abbrev.upper())


def team_to_kalshi_abbrev(team_name: str) -> str | None:
    """Convert a canonical team name to Kalshi ticker abbreviation."""
    normalized = normalize_team_name(team_name)
    return _TEAM_TO_KALSHI.get(normalized)
