"""Simple retrieve + generate chain for RAGAS evaluation.

This is a minimal RAG pipeline used for baseline and advanced retrieval evals.
The full LangGraph agent (with tools) is built in a later step.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from app.retrieval.qdrant_store import QdrantRetrievalService
from app.retrieval.reranker import build_reranked_retriever, rerank_search
from app.settings import settings

_RAG_PROMPT = (
    "You are an NHL analytics assistant. Use ONLY the provided context to answer "
    "the question. If the context does not contain enough information, say so.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


@dataclass(slots=True)
class RAGResult:
    response: str
    retrieved_contexts: list[str]
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


def _generate(llm: ChatOpenAI, question: str, contexts: list[str]) -> RAGResult:
    """Format prompt, call LLM, and return RAGResult with token usage."""
    context_block = "\n\n".join(contexts)
    prompt = _RAG_PROMPT.format(context=context_block, question=question)
    response = llm.invoke(prompt)
    token_usage = response.response_metadata.get("token_usage", {})
    input_tokens = token_usage.get("input_tokens", token_usage.get("prompt_tokens"))
    output_tokens = token_usage.get("output_tokens", token_usage.get("completion_tokens"))
    total_tokens = token_usage.get("total_tokens")
    return RAGResult(
        response=response.content,
        retrieved_contexts=contexts,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _default_llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.OPENAI_MODEL, api_key=settings.OPENAI_API_KEY)


def build_rag_chain(
    retrieval_service: QdrantRetrievalService | None = None,
    llm: ChatOpenAI | None = None,
    retrieval_limit: int = 6,
) -> callable:
    """Return a function that takes a question and returns a RAGResult."""
    if retrieval_service is None:
        retrieval_service = QdrantRetrievalService()
    if llm is None:
        llm = _default_llm()

    def invoke(question: str) -> RAGResult:
        docs = retrieval_service.search(question, limit=retrieval_limit)
        return _generate(llm, question, [doc.text for doc in docs])

    return invoke


def build_reranked_rag_chain(
    retrieval_service: QdrantRetrievalService | None = None,
    llm: ChatOpenAI | None = None,
    initial_k: int = 10,
    top_n: int = 5,
) -> callable:
    """Return a function that takes a question and returns a RAGResult.

    Uses Cohere reranking: retrieve initial_k from Qdrant, rerank to top_n.
    """
    if retrieval_service is None:
        retrieval_service = QdrantRetrievalService()
    if llm is None:
        llm = _default_llm()

    retriever = build_reranked_retriever(
        service=retrieval_service,
        initial_k=initial_k,
        top_n=top_n,
    )

    def invoke(question: str) -> RAGResult:
        docs = rerank_search(question, retriever)
        return _generate(llm, question, [doc.text for doc in docs])

    return invoke
