"""Odds conversion and de-vigging utilities.

All functions are pure — no API calls, no LLM calls.
"""

from __future__ import annotations


def american_to_implied(odds: int) -> float:
    """Convert American odds to raw implied probability (0-1).

    Positive odds (e.g. +150): 100 / (odds + 100)
    Negative odds (e.g. -200): -odds / (-odds + 100)
    """
    if odds > 0:
        return 100.0 / (odds + 100.0)
    elif odds < 0:
        return -odds / (-odds + 100.0)
    else:
        return 0.5


def devig_multiplicative(probs: list[float]) -> list[float]:
    """Remove vig by normalizing implied probabilities to sum to 1.0.

    Multiplicative method: divide each prob by total.
    """
    total = sum(probs)
    if total == 0:
        return probs
    return [p / total for p in probs]


def compute_edge(fair_prob: float, kalshi_prob: float) -> float:
    """Compute edge: fair_prob - kalshi_prob.

    Positive edge means the fair probability exceeds Kalshi's implied price.
    """
    return fair_prob - kalshi_prob
