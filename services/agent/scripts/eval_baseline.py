"""CLI: run baseline RAGAS evaluation on the golden dataset."""

from __future__ import annotations

import json
import sys
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
        result = rag(question)
        eval_samples.append({
            "user_input": question,
            "response": result.response,
            "retrieved_contexts": result.retrieved_contexts,
            "reference": example.get("reference", ""),
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
        if col in scores.columns:
            avg = scores[col].mean()
            print(f"  {col}: {avg:.4f}")

    # Save results
    results_data = {
        "revision_id": "baseline",
        "retrieval": "dense_cosine_qdrant",
        "retrieval_limit": 6,
        "num_examples": len(examples),
        "metrics": {
            col: float(scores[col].mean())
            for col in metric_cols
            if col in scores.columns
        },
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(results_data, indent=2), encoding="utf-8"
    )
    print(f"\nresults saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
