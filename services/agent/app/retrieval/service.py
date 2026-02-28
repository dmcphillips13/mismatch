"""Typed retrieval result and citation conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RetrievedDocument:
    id: str
    text: str
    score: float
    metadata: dict[str, Any]

    def to_citation(self) -> dict[str, Any]:
        teams = self.metadata.get("teams")
        if teams and isinstance(teams, list) and len(teams) >= 2:
            label = f"{teams[0]} vs {teams[1]}"
        else:
            label = self.metadata.get("team")
        return {
            "id": self.id,
            "label": label,
            "season_id": self.metadata.get("season_id"),
            "doc_type": self.metadata.get("doc_type"),
            "source": "qdrant",
            "metadata": self.metadata,
        }
