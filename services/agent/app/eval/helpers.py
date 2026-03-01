"""Shared eval utilities for baseline and advanced RAGAS evaluation scripts."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.metrics._context_entities_recall import ContextEntityRecall
from ragas.metrics._context_precision import ContextPrecision
from ragas.metrics._context_recall import ContextRecall
from ragas.metrics._factual_correctness import FactualCorrectness
from ragas.metrics._faithfulness import Faithfulness

from app.settings import settings

MODEL_PRICING_PER_1M_TOKENS = {
    # USD per 1M tokens
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

METRIC_COLS = [
    "faithfulness",
    "context_precision",
    "context_recall",
    "context_entity_recall",
    "answer_relevancy",
    "factual_correctness",
]

RAGAS_METRICS = [
    Faithfulness(),
    ContextPrecision(),
    ContextRecall(),
    ContextEntityRecall(),
    AnswerRelevancy(),
    FactualCorrectness(),
]


def build_evaluator() -> tuple[LangchainLLMWrapper, LangchainEmbeddingsWrapper]:
    """Return (evaluator_llm, evaluator_embeddings) for RAGAS evaluate()."""
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model=settings.OPENAI_MODEL, api_key=settings.OPENAI_API_KEY)
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDINGS_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
    )
    return evaluator_llm, evaluator_embeddings


def _safe_float(value: object) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def _get_metric_value(score_row: dict, metric_key: str) -> float | None:
    """Read metric values, handling RAGAS suffix variants like '(mode=f1)'."""
    direct = _safe_float(score_row.get(metric_key))
    if direct is not None:
        return direct
    for key, value in score_row.items():
        if key.startswith(metric_key):
            parsed = _safe_float(value)
            if parsed is not None:
                return parsed
    return None


def get_metric_average(scores_df, metric_key: str) -> float | None:
    if metric_key in scores_df.columns:
        return float(scores_df[metric_key].mean())
    for col in scores_df.columns:
        if col.startswith(metric_key):
            return float(scores_df[col].mean())
    return None


def estimate_rag_cost_usd(
    model_name: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    pricing = MODEL_PRICING_PER_1M_TOKENS.get(model_name)
    if not pricing:
        return None
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)


def upload_results_to_langsmith(
    eval_samples: list[dict],
    score_rows: list[dict],
    revision_id: str,
    dataset_name: str,
    results_path: Path,
    script_name: str,
) -> None:
    """Upload per-query eval metrics to LangSmith for run-to-run comparison."""
    if not settings.LANGSMITH_API_KEY:
        print("LANGSMITH_API_KEY not set — skipping LangSmith results upload")
        return

    try:
        from langsmith import Client

        client = Client(api_key=settings.LANGSMITH_API_KEY)
        try:
            dataset = client.read_dataset(dataset_name=dataset_name)
            client.delete_dataset(dataset_id=dataset.id)
            dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Per-query RAGAS eval metrics for Mismatch",
            )
        except Exception:
            dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Per-query RAGAS eval metrics for Mismatch",
            )

        upload_count = 0
        for sample, score_row in zip(eval_samples, score_rows):
            outputs = {
                "faithfulness": _get_metric_value(score_row, "faithfulness"),
                "context_precision": _get_metric_value(score_row, "context_precision"),
                "context_recall": _get_metric_value(score_row, "context_recall"),
                "context_entity_recall": _get_metric_value(score_row, "context_entity_recall"),
                "answer_relevancy": _get_metric_value(score_row, "answer_relevancy"),
                "factual_correctness": _get_metric_value(score_row, "factual_correctness"),
                "latency_ms": _safe_float(sample.get("latency_ms")),
                "cost_usd": _safe_float(sample.get("cost_usd")),
            }
            client.create_example(
                inputs={
                    "run_type": "ragas_eval_per_query",
                    "question": sample["user_input"],
                    "revision_id": revision_id,
                },
                outputs=outputs,
                metadata={
                    "reference": sample.get("reference", ""),
                    "retrieved_context_count": len(sample.get("retrieved_contexts", [])),
                    "metric_faithfulness": outputs["faithfulness"],
                    "metric_context_precision": outputs["context_precision"],
                    "metric_context_recall": outputs["context_recall"],
                    "metric_context_entity_recall": outputs["context_entity_recall"],
                    "metric_answer_relevancy": outputs["answer_relevancy"],
                    "metric_factual_correctness": outputs["factual_correctness"],
                    "latency_ms": outputs["latency_ms"],
                    "cost_usd": outputs["cost_usd"],
                    "evaluated_at": datetime.now(UTC).isoformat(),
                    "results_path": str(results_path),
                    "script": script_name,
                },
                dataset_id=dataset.id,
            )
            upload_count += 1
        print(
            f"uploaded {upload_count} per-query results to LangSmith dataset "
            f"'{dataset_name}'"
        )
    except Exception as e:
        print(f"warning: LangSmith results upload failed: {e}")
