"""CLI: run advanced retrieval (Cohere rerank) RAGAS evaluation and compare with baseline."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ragas import EvaluationDataset, RunConfig, evaluate

from app.eval.helpers import (
    METRIC_COLS,
    RAGAS_METRICS,
    get_metric_average,
    build_evaluator,
    estimate_rag_cost_usd,
    upload_results_to_langsmith,
)
from app.eval.rag_chain import build_reranked_rag_chain
from app.settings import settings

TESTSET_PATH = Path("data/eval/testset.json")
BASELINE_RESULTS_PATH = Path("data/eval/baseline_results.json")
RESULTS_PATH = Path("data/eval/advanced_results.json")
LANGSMITH_RESULTS_DATASET = "mismatch-eval-advanced"

INITIAL_K = 10
RERANK_TOP_N = 5


def _print_comparison(baseline_metrics: dict, advanced_metrics: dict) -> None:
    """Print a side-by-side comparison table of baseline vs advanced metrics."""
    print("\n=== BASELINE vs ADVANCED COMPARISON ===")
    print(f"  {'metric':<30} {'baseline':>10} {'advanced':>10} {'delta':>10}")
    print(f"  {'-' * 30} {'-' * 10} {'-' * 10} {'-' * 10}")
    for col in METRIC_COLS:
        b = baseline_metrics.get(col)
        a = advanced_metrics.get(col)
        if b is not None and a is not None:
            delta = a - b
            sign = "+" if delta >= 0 else ""
            print(f"  {col:<30} {b:>10.4f} {a:>10.4f} {sign}{delta:>9.4f}")
        elif a is not None:
            print(f"  {col:<30} {'n/a':>10} {a:>10.4f} {'':>10}")
        elif b is not None:
            print(f"  {col:<30} {b:>10.4f} {'n/a':>10} {'':>10}")


def main() -> None:
    if not TESTSET_PATH.exists():
        print(f"error: {TESTSET_PATH} does not exist. Run generate_testset.py first.")
        sys.exit(1)

    examples = json.loads(TESTSET_PATH.read_text(encoding="utf-8"))
    print(f"loaded {len(examples)} test examples")

    # Build reranked RAG chain
    print(f"building reranked RAG chain (initial_k={INITIAL_K}, top_n={RERANK_TOP_N})...")
    rag = build_reranked_rag_chain(initial_k=INITIAL_K, top_n=RERANK_TOP_N)

    # Run RAG on each example
    print("running reranked RAG chain on test examples...")
    eval_samples = []
    total_input_tokens = 0
    total_output_tokens = 0
    latencies = []
    for i, example in enumerate(examples):
        question = example["user_input"]
        started_at = time.perf_counter()
        result = rag(question)
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        cost_usd = estimate_rag_cost_usd(
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
        if result.input_tokens:
            total_input_tokens += result.input_tokens
        if result.output_tokens:
            total_output_tokens += result.output_tokens
        latencies.append(latency_ms)
        print(f"  [{i + 1}/{len(examples)}] {question[:60]}...")

    # Build RAGAS EvaluationDataset
    dataset = EvaluationDataset.from_list(eval_samples)

    # Run RAGAS evaluation
    print("running RAGAS evaluation...")
    evaluator_llm, evaluator_embeddings = build_evaluator()

    result = evaluate(
        dataset=dataset,
        metrics=RAGAS_METRICS,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=RunConfig(timeout=360),
    )

    # Print results
    print("\n=== ADVANCED RAGAS RESULTS (Cohere Rerank) ===")
    scores = result.to_pandas()
    advanced_metrics = {}
    for col in METRIC_COLS:
        avg = get_metric_average(scores, col)
        if avg is not None:
            advanced_metrics[col] = avg
            print(f"  {col}: {avg:.4f}")

    # Compute performance stats
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    sorted_latencies = sorted(latencies)
    p95_idx = int(len(sorted_latencies) * 0.95)
    p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
    total_cost = estimate_rag_cost_usd(
        model_name=settings.OPENAI_MODEL,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
    )
    avg_cost = total_cost / len(examples) if total_cost else None

    # Save results
    results_data = {
        "revision_id": "cohere_rerank",
        "retrieval": "dense_cosine_qdrant+cohere_rerank_v3.5",
        "retrieval_limit": INITIAL_K,
        "rerank_top_n": RERANK_TOP_N,
        "num_examples": len(examples),
        "metrics": advanced_metrics,
        "performance": {
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "avg_cost_usd": avg_cost,
            "total_cost_usd": total_cost,
            "sample_count": len(examples),
        },
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(results_data, indent=2), encoding="utf-8"
    )
    print(f"\nresults saved to {RESULTS_PATH}")

    # Print comparison with baseline
    if BASELINE_RESULTS_PATH.exists():
        baseline_data = json.loads(BASELINE_RESULTS_PATH.read_text(encoding="utf-8"))
        baseline_metrics = baseline_data.get("metrics", {})
        _print_comparison(baseline_metrics, advanced_metrics)
    else:
        print(f"\nwarning: {BASELINE_RESULTS_PATH} not found — skipping comparison")

    # Upload to LangSmith
    upload_results_to_langsmith(
        eval_samples=eval_samples,
        score_rows=scores.to_dict(orient="records"),
        revision_id=results_data["revision_id"],
        dataset_name=LANGSMITH_RESULTS_DATASET,
        results_path=RESULTS_PATH,
        script_name="scripts/eval_advanced.py",
    )


if __name__ == "__main__":
    main()
