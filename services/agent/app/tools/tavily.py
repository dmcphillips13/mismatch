"""Tavily client — web search for injuries, goalies, and news context."""

from __future__ import annotations

import httpx

from app.settings import settings
from app.tools.models import TavilyResult


class TavilyClient:
    """Thin httpx wrapper around the Tavily search API."""

    def __init__(self) -> None:
        if not settings.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY is required")
        self._base_url = settings.TAVILY_API_BASE_URL

    def search(self, query: str, max_results: int = 5) -> list[TavilyResult]:
        """Run a Tavily web search and return parsed results."""
        resp = httpx.post(
            f"{self._base_url}/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
            },
            timeout=15,
        )
        resp.raise_for_status()

        return [
            TavilyResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in resp.json().get("results", [])
        ]
