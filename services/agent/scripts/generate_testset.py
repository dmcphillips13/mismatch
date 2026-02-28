"""CLI: generate synthetic eval dataset from docs.jsonl using RAGAS TestsetGenerator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import (
    MultiHopAbstractQuerySynthesizer,
    MultiHopSpecificQuerySynthesizer,
    SingleHopSpecificQuerySynthesizer,
)

from app.settings import settings

TESTSET_OUTPUT = Path("data/eval/testset.json")

# Hand-crafted questions focused on matchup analysis — Mismatch's core use case
HAND_CRAFTED = [
    {
        "user_input": "How have the Bruins and Maple Leafs done head-to-head in 2024-25?",
        "reference": "The Bruins vs Maple Leafs 2024-25 head-to-head season summary shows their win/loss record, goals for/against, and home/away splits.",
    },
    {
        "user_input": "What's the recent matchup history between the Panthers and Lightning?",
        "reference": "The Panthers vs Lightning recent head-to-head summary covers their last 8 meetings across seasons with record, goals, and OT/SO counts.",
    },
    {
        "user_input": "Who has the edge when the Rangers play the Penguins at home?",
        "reference": "The Rangers vs Penguins head-to-head summaries include home/away splits showing each team's home win count in the matchup.",
    },
    {
        "user_input": "How did the Capitals vs Penguins matchup in 2023-24 compare to 2024-25?",
        "reference": "Comparing the Capitals vs Penguins h2h_season docs for 2023-24 and 2024-25 shows how the rivalry shifted year over year.",
    },
    {
        "user_input": "Are the Jets on a hot streak, and how have they done against the Wild recently?",
        "reference": "The Jets' recent form summary shows their current streak, while the Jets vs Wild recent h2h summary shows their head-to-head record.",
    },
    {
        "user_input": "Have the Oilers or the Flames won more head-to-head games in 2024-25?",
        "reference": "The Calgary Flames vs Edmonton Oilers 2024-25 h2h_season summary shows each team's win count in their Battle of Alberta matchups.",
    },
    {
        "user_input": "How many overtime or shootout games have the Avalanche and Stars played recently?",
        "reference": "The Avalanche vs Stars recent h2h summary includes the OT/SO game count across their last 8 meetings.",
    },
    {
        "user_input": "Which team scores more goals in the Hurricanes vs Devils matchup in 2024-25?",
        "reference": "The Hurricanes vs Devils 2024-25 h2h_season summary includes total goals for each team across their season meetings.",
    },
    {
        "user_input": "What is the Maple Leafs' overall season form in 2024-25 and how does it compare to their record against the Canadiens?",
        "reference": "The Maple Leafs' 2024-25 team_season_summary shows their overall win rate, while the Canadiens vs Maple Leafs h2h_season summary shows matchup-specific results.",
    },
    {
        "user_input": "How have the Golden Knights and Kings matched up across the last few seasons?",
        "reference": "The Golden Knights vs Kings recent h2h summary covers their last 8 meetings across multiple seasons with record, goals, and home/away splits.",
    },
]


def load_docs_as_langchain(docs_path: Path) -> list[Document]:
    """Load docs.jsonl and convert to LangChain Document objects."""
    documents: list[Document] = []
    for line in docs_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        documents.append(
            Document(
                page_content=doc["text"],
                metadata=doc["metadata"],
            )
        )
    return documents


def main() -> None:
    docs_path = settings.PROCESSED_DATA_PATH
    if not docs_path.exists():
        print(f"error: {docs_path} does not exist. Run build_docs.py first.")
        sys.exit(1)

    print(f"loading docs from {docs_path}")
    documents = load_docs_as_langchain(docs_path)
    print(f"loaded {len(documents)} documents")

    generator_llm = LangchainLLMWrapper(
        ChatOpenAI(model=settings.OPENAI_MODEL, api_key=settings.OPENAI_API_KEY)
    )
    embedding_model = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDINGS_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
    )

    generator = TestsetGenerator(
        llm=generator_llm, embedding_model=embedding_model
    )

    query_distribution = [
        (SingleHopSpecificQuerySynthesizer(llm=generator_llm), 0.5),
        (MultiHopAbstractQuerySynthesizer(llm=generator_llm), 0.25),
        (MultiHopSpecificQuerySynthesizer(llm=generator_llm), 0.25),
    ]

    testset_size = 10
    print(f"generating synthetic testset (~{testset_size} examples)...")
    synthetic_rows: list[dict] = []
    try:
        testset = generator.generate_with_langchain_docs(
            documents,
            testset_size=testset_size,
            query_distribution=query_distribution,
        )
        synthetic_rows = testset.to_pandas().to_dict(orient="records")
        print(f"generated {len(synthetic_rows)} synthetic examples")
    except Exception as e:
        print(f"warning: synthetic generation failed: {e}")
        print("continuing with hand-crafted examples only")

    # Combine synthetic + hand-crafted
    all_examples = []
    for row in synthetic_rows:
        all_examples.append({
            "user_input": str(row.get("user_input", "")),
            "reference": str(row.get("reference", "")),
            "reference_contexts": row.get("reference_contexts", []),
            "source": "synthetic",
        })
    for hc in HAND_CRAFTED:
        all_examples.append({
            "user_input": hc["user_input"],
            "reference": hc["reference"],
            "reference_contexts": [],
            "source": "hand_crafted",
        })

    # Save locally
    TESTSET_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TESTSET_OUTPUT.write_text(
        json.dumps(all_examples, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"saved {len(all_examples)} examples to {TESTSET_OUTPUT}")

    # Upload to LangSmith if configured
    if settings.LANGSMITH_API_KEY:
        try:
            from langsmith import Client

            client = Client(api_key=settings.LANGSMITH_API_KEY)
            dataset_name = "mismatch-golden-dataset"

            # Delete existing dataset with same name if it exists
            try:
                existing = client.read_dataset(dataset_name=dataset_name)
                client.delete_dataset(dataset_id=existing.id)
                print(f"deleted existing LangSmith dataset '{dataset_name}'")
            except Exception:
                pass

            ls_dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Golden eval dataset for Mismatch RAG (synthetic + hand-crafted)",
            )
            for example in all_examples:
                client.create_example(
                    inputs={"question": example["user_input"]},
                    outputs={"answer": example["reference"]},
                    metadata={
                        "source": example["source"],
                        "reference_contexts": example["reference_contexts"],
                    },
                    dataset_id=ls_dataset.id,
                )
            print(f"uploaded {len(all_examples)} examples to LangSmith dataset '{dataset_name}'")
        except Exception as e:
            print(f"warning: LangSmith upload failed: {e}")
            print("dataset saved locally — you can upload later")
    else:
        print("LANGSMITH_API_KEY not set — skipping LangSmith upload")


if __name__ == "__main__":
    main()
