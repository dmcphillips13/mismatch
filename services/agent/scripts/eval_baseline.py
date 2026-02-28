"""CLI: run baseline RAGAS evaluation on the golden dataset."""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.metrics._context_entities_recall import ContextEntityRecall
from ragas.metrics._context_recall import ContextRecall
from ragas.metrics._factual_correctness import FactualCorrectness
from ragas.metrics._faithfulness import Faithfulness

from app.eval.rag_chain import build_rag_chain
from app.settings import settings

TESTSET_PATH = Path("data/eval/testset.json")
RESULTS_PATH = Path("data/eval/baseline_results.json")
LANGSMITH_RESULTS_DATASET = "mismatch-eval-results"
MODEL_PRICING_PER_1M_TOKENS = {
    # USD per 1M tokens
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


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


def _get_metric_average(scores_df, metric_key: str) -> float | None:
    if metric_key in scores_df.columns:
        return float(scores_df[metric_key].mean())
    for col in scores_df.columns:
        if col.startswith(metric_key):
            return float(scores_df[col].mean())
    return None


def _estimate_rag_cost_usd(
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
    eval_samples: list[dict], score_rows: list[dict], revision_id: str
) -> None:
    """Upload per-query eval metrics to LangSmith for run-to-run comparison."""
    if not settings.LANGSMITH_API_KEY:
        print("LANGSMITH_API_KEY not set — skipping LangSmith results upload")
        return

    try:
        from langsmith import Client

        client = Client(api_key=settings.LANGSMITH_API_KEY)
        try:
            dataset = client.read_dataset(dataset_name=LANGSMITH_RESULTS_DATASET)
            client.delete_dataset(dataset_id=dataset.id)
            dataset = client.create_dataset(
                dataset_name=LANGSMITH_RESULTS_DATASET,
                description="Per-query RAGAS eval metrics for Mismatch",
            )
        except Exception:
            dataset = client.create_dataset(
                dataset_name=LANGSMITH_RESULTS_DATASET,
                description="Per-query RAGAS eval metrics for Mismatch",
            )

        upload_count = 0
        for sample, score_row in zip(eval_samples, score_rows):
            outputs = {
                "faithfulness": _get_metric_value(score_row, "faithfulness"),
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
                    "metric_context_recall": outputs["context_recall"],
                    "metric_context_entity_recall": outputs["context_entity_recall"],
                    "metric_answer_relevancy": outputs["answer_relevancy"],
                    "metric_factual_correctness": outputs["factual_correctness"],
                    "latency_ms": outputs["latency_ms"],
                    "cost_usd": outputs["cost_usd"],
                    "evaluated_at": datetime.now(UTC).isoformat(),
                    "results_path": str(RESULTS_PATH),
                    "script": "scripts/eval_baseline.py",
                },
                dataset_id=dataset.id,
            )
            upload_count += 1
        print(
            f"uploaded {upload_count} per-query results to LangSmith dataset "
            f"'{LANGSMITH_RESULTS_DATASET}'"
        )
    except Exception as e:
        print(f"warning: LangSmith results upload failed: {e}")


def main() -> None:
    if not TESTSET_PATH.exists():
        print(f"error: {TESTSET_PATH} does not exist. Run generate_testset.py first.")
        sys.exit(1)

    examples = json.loads(TESTSET_PATH.read_text(encoding="utf-8"))
    print(f"loaded {len(examples)} test examples")

    # Build baseline RAG chain
    print("building baseline RAG chain...")
    rag = build_rag_chain(retrieval_limit=6)

    # Run RAG on each example
    print("running RAG chain on test examples...")
    eval_samples = []
    for i, example in enumerate(examples):
        question = example["user_input"]
        started_at = time.perf_counter()
        result = rag(question)
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        cost_usd = _estimate_rag_cost_usd(
            model_name=settings.OPENAI_MODEL,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        eval_samples.append({
            "user_input": question,
            "response": result.response,
            "retrieved_contexts": result.retrieved_contexts,
            "reference": example.get("reference", ""),
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
        })
        print(f"  [{i + 1}/{len(examples)}] {question[:60]}...")

    # Build RAGAS EvaluationDataset
    dataset = EvaluationDataset.from_list(eval_samples)

    # Run RAGAS evaluation
    print("running RAGAS evaluation...")
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model=settings.OPENAI_MODEL, api_key=settings.OPENAI_API_KEY)
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDINGS_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
    )

    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            ContextRecall(),
            ContextEntityRecall(),
            AnswerRelevancy(),
            FactualCorrectness(),
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=RunConfig(timeout=360),
    )

    # Print results
    print("\n=== BASELINE RAGAS RESULTS ===")
    scores = result.to_pandas()
    metric_cols = [
        "faithfulness",
        "context_recall",
        "context_entity_recall",
        "answer_relevancy",
        "factual_correctness",
    ]
    for col in metric_cols:
        avg = _get_metric_average(scores, col)
        if avg is not None:
            print(f"  {col}: {avg:.4f}")

    # Save results
    results_data = {
        "revision_id": "baseline",
        "retrieval": "dense_cosine_qdrant",
        "retrieval_limit": 6,
        "num_examples": len(examples),
        "metrics": {
            col: avg
            for col in metric_cols
            if (avg := _get_metric_average(scores, col)) is not None
        },
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(results_data, indent=2), encoding="utf-8"
    )
    print(f"\nresults saved to {RESULTS_PATH}")
    upload_results_to_langsmith(
        eval_samples=eval_samples,
        score_rows=scores.to_dict(orient="records"),
        revision_id=results_data["revision_id"],
    )


if __name__ == "__main__":
    main()
