"""Bulk-index the files listed in data/source_register.csv."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.config import get_settings
from app.rag.loader import load_file
from app.rag.store import get_store, list_register


def ingest_documents(reset: bool = False) -> list[tuple[str, int]]:
    settings = get_settings()
    register_path = Path(settings.source_register_path).resolve()
    if not register_path.is_file():
        raise FileNotFoundError(f"Source Register not found: {register_path}")

    store = get_store()
    if reset:
        for entry in list_register():
            store.delete_document(entry["doc_id"])

    results = []
    with register_path.open(newline="", encoding="utf-8-sig") as register_file:
        rows = csv.DictReader(register_file)
        if not {"doc_id", "file"}.issubset(rows.fieldnames or []):
            raise ValueError("Source Register must include doc_id and file columns")
        for row in rows:
            source_path = (register_path.parent / row["file"]).resolve()
            if not source_path.is_relative_to(register_path.parent.resolve()):
                raise ValueError(f"source path escapes the data directory: {row['file']}")
            if not source_path.is_file():
                raise FileNotFoundError(f"Registered source not found: {source_path}")
            document = load_file(source_path, row)
            if not document.text.strip():
                raise ValueError(f"Registered source has no extractable text: {source_path}")
            results.append((document.metadata.doc_id, store.index_document(document)))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="remove existing registered documents first")
    args = parser.parse_args()
    results = ingest_documents(reset=args.reset)
    for doc_id, count in results:
        print(f"{doc_id}: indexed {count} chunks")
    print(f"Indexed {len(results)} documents")


if __name__ == "__main__":
    main()
