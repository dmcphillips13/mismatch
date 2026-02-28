"""Typed result models for tool outputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GameOdds:
    """De-vigged fair probabilities for an NHL game from the odds aggregator."""

    home_team: str
    away_team: str
    home_fair_prob: float
    away_fair_prob: float
    commence_time: str
    bookmakers_used: int


@dataclass(slots=True)
class KalshiMarket:
    """A single Kalshi NHL game market (one per team per game)."""

    ticker: str
    team: str
    yes_ask: float  # 0-1 implied probability
    yes_bid: float  # 0-1 implied probability
    opponent: str
    game_date: str


@dataclass(slots=True)
class MatchupEdge:
    """Matched game with edge computation for both sides."""

    home_team: str
    away_team: str
    home_fair_prob: float
    away_fair_prob: float
    kalshi_home_prob: float | None
    kalshi_away_prob: float | None
    home_edge: float | None
    away_edge: float | None
    recommendation: str  # "BET" | "PASS" | "NO_MARKET"
    game_date: str


@dataclass(slots=True)
class TavilyResult:
    """A single search result from Tavily."""

    title: str
    url: str
    snippet: str
