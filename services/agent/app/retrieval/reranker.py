"""Cohere reranking layer using ContextualCompressionRetriever.

Follows AIE9 Session 11 pattern: CohereRerank + ContextualCompressionRetriever
wrapping a thin LangChain BaseRetriever adapter over QdrantRetrievalService.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.retrieval.qdrant_store import QdrantRetrievalService
from app.retrieval.service import RetrievedDocument
from app.settings import settings


class QdrantLangChainRetriever(BaseRetriever):
    """Thin adapter exposing QdrantRetrievalService as a LangChain BaseRetriever."""

    service: Any  # QdrantRetrievalService (Any to satisfy pydantic)
    k: int = 10

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> list[Document]:
        docs = self.service.search(query, limit=self.k)
        return [
            Document(
                page_content=doc.text,
                metadata={
                    **doc.metadata,
                    "_retrieval_id": doc.id,
                    "_retrieval_score": doc.score,
                },
            )
            for doc in docs
        ]


def build_reranked_retriever(
    service: QdrantRetrievalService | None = None,
    initial_k: int = 10,
    top_n: int = 5,
) -> ContextualCompressionRetriever:
    """Create a ContextualCompressionRetriever with CohereRerank."""
    if service is None:
        service = QdrantRetrievalService()

    base_retriever = QdrantLangChainRetriever(service=service, k=initial_k)
    compressor = CohereRerank(
        model=settings.COHERE_RERANK_MODEL,
        top_n=top_n,
        cohere_api_key=settings.COHERE_API_KEY,
    )
    return ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever,
    )


def rerank_search(
    query: str,
    retriever: ContextualCompressionRetriever,
    max_retries: int = 5,
) -> list[RetrievedDocument]:
    """Invoke the compression retriever and convert back to RetrievedDocument.

    Retries with exponential backoff on Cohere rate-limit (429) errors.
    """
    for attempt in range(max_retries):
        try:
            lc_docs = retriever.invoke(query)
            break
        except Exception as e:
            if "429" in str(e) or "too_many_requests" in type(e).__name__.lower():
                wait = 2 ** attempt * 7  # 7s, 14s, 28s, 56s, 112s
                print(f"  rate limited, retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise
    else:
        raise RuntimeError(f"Cohere rerank failed after {max_retries} retries")
    return [
        RetrievedDocument(
            id=doc.metadata.get("_retrieval_id", ""),
            text=doc.page_content,
            score=doc.metadata.get("relevance_score", 0.0),
            metadata={
                k: v
                for k, v in doc.metadata.items()
                if not k.startswith("_retrieval_")
                and k != "relevance_score"
            },
        )
        for doc in lc_docs
    ]
