"""CLI: run baseline RAGAS evaluation on the golden dataset."""

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
from app.eval.rag_chain import build_rag_chain
from app.settings import settings

TESTSET_PATH = Path("data/eval/testset.json")
RESULTS_PATH = Path("data/eval/baseline_results.json")
LANGSMITH_RESULTS_DATASET = "mismatch-eval-baseline"


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
    print("\n=== BASELINE RAGAS RESULTS ===")
    scores = result.to_pandas()
    for col in METRIC_COLS:
        avg = get_metric_average(scores, col)
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
            for col in METRIC_COLS
            if (avg := get_metric_average(scores, col)) is not None
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
        dataset_name=LANGSMITH_RESULTS_DATASET,
        results_path=RESULTS_PATH,
        script_name="scripts/eval_baseline.py",
    )


if __name__ == "__main__":
    main()
