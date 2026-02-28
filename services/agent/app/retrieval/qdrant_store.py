"""Qdrant-backed retrieval and upsert helpers."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.clients.openai_embeddings import EmbeddingClient
from app.retrieval.service import RetrievedDocument
from app.settings import settings

# Namespace UUID for deterministic id generation from string doc ids
_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


class QdrantRetrievalService:
    """Embeds queries and performs similarity search with optional payload filters."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        if client is None:
            if not settings.QDRANT_URL:
                raise ValueError("QDRANT_URL is required for retrieval")
            client = QdrantClient(
                url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY
            )
        self._client = client
        self._embeddings = embedding_client or EmbeddingClient()

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        collections = {
            c.name for c in self._client.get_collections().collections
        }
        if settings.QDRANT_COLLECTION in collections:
            return
        self._client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=settings.OPENAI_EMBEDDINGS_DIMENSIONS,
                distance=models.Distance.COSINE,
            ),
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 6,
        teams: list[str] | None = None,
        season_ids: list[str] | None = None,
        doc_types: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        """Embed the query and perform filtered similarity search."""
        query_vector = self._embeddings.embed_texts([query])[0]
        query_filter = _build_filter(
            teams=teams, season_ids=season_ids, doc_types=doc_types
        )
        points = self._client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            RetrievedDocument(
                id=str(point.payload.get("doc_id", point.id)),
                text=str(point.payload.get("text", "")),
                score=float(point.score),
                metadata=dict(point.payload.get("metadata", {})),
            )
            for point in points
        ]

    def upsert_jsonl(self, docs_path: Path) -> int:
        """Read docs.jsonl, embed, and upsert all points to Qdrant."""
        self.ensure_collection()
        docs: list[dict[str, Any]] = [
            json.loads(line)
            for line in docs_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not docs:
            return 0

        # Batch embed in chunks of 100 to stay under API limits
        batch_size = 100
        all_points: list[models.PointStruct] = []
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            vectors = self._embeddings.embed_texts([d["text"] for d in batch])
            for doc, vector in zip(batch, vectors, strict=True):
                point_id = str(uuid.uuid5(_NAMESPACE, doc["id"]))
                all_points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "doc_id": doc["id"],
                            "text": doc["text"],
                            "metadata": doc["metadata"],
                        },
                    )
                )

        # Upsert in batches of 100
        for i in range(0, len(all_points), batch_size):
            self._client.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=all_points[i : i + batch_size],
            )
        return len(all_points)


def _build_filter(
    *,
    teams: list[str] | None = None,
    season_ids: list[str] | None = None,
    doc_types: list[str] | None = None,
) -> models.Filter | None:
    """Build a Qdrant filter from optional field constraints."""
    conditions: list[models.FieldCondition] = []
    if teams:
        conditions.append(
            models.FieldCondition(
                key="metadata.team", match=models.MatchAny(any=teams)
            )
        )
    if season_ids:
        conditions.append(
            models.FieldCondition(
                key="metadata.season_id",
                match=models.MatchAny(any=season_ids),
            )
        )
    if doc_types:
        conditions.append(
            models.FieldCondition(
                key="metadata.doc_type",
                match=models.MatchAny(any=doc_types),
            )
        )
    if not conditions:
        return None
    return models.Filter(must=conditions)
