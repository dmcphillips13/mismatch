"""CLI: upsert processed documents into Qdrant."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/upsert_docs.py` from services/agent/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retrieval.qdrant_store import QdrantRetrievalService
from app.settings import settings


def main() -> None:
    docs_path = settings.PROCESSED_DATA_PATH
    if not docs_path.exists():
        print(f"error: {docs_path} does not exist. Run build_docs.py first.")
        sys.exit(1)

    service = QdrantRetrievalService()
    count = service.upsert_jsonl(docs_path)
    print(f"upserted {count} docs to collection '{settings.QDRANT_COLLECTION}'")


if __name__ == "__main__":
    main()
