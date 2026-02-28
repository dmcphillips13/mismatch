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
        return {
            "id": self.id,
            "label": self.metadata.get("team"),
            "season_id": self.metadata.get("season_id"),
            "doc_type": self.metadata.get("doc_type"),
            "source": "qdrant",
            "metadata": self.metadata,
        }
