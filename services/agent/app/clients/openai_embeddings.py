"""OpenAI embeddings wrapper used by retrieval and ingestion."""

from __future__ import annotations

from openai import OpenAI

from app.settings import settings


class EmbeddingClient:
    """Small synchronous wrapper around the OpenAI embeddings API."""

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=settings.OPENAI_EMBEDDINGS_MODEL,
            input=texts,
            dimensions=settings.OPENAI_EMBEDDINGS_DIMENSIONS,
        )
        return [item.embedding for item in response.data]
