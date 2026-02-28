"""CLI: build retrieval documents from raw CSV inputs."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/build_docs.py` from services/agent/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.build_docs import build_documents, chunk_documents, write_documents
from app.settings import settings


def main() -> None:
    raw_dir = settings.RAW_DATA_DIR.resolve()
    output = settings.PROCESSED_DATA_PATH

    print(f"reading CSVs from {raw_dir}")
    docs, logs = build_documents(raw_dir)
    raw_count = len(docs)
    docs = chunk_documents(docs)
    write_documents(output, docs)
    print(f"built {raw_count} docs, chunked to {len(docs)} docs, wrote to {output}")
    for line in logs:
        print(line)


if __name__ == "__main__":
    main()
