"""
Ingest documents listed in data/source_register.csv (Annex B) into ChromaDB.

    python scripts/ingest_documents.py                 # every row in the register
    python scripts/ingest_documents.py --reset         # wipe the collection first
    python scripts/ingest_documents.py path/to/doc.md  # one file (front-matter metadata)
    python scripts/ingest_documents.py path/to/doc.pdf --metadata '{"doc_id": "...", ...}'

Chroma is persisted to disk, so this is NOT re-run on every restart (guide §5). Re-running is
safe: documents are keyed by doc_id and replaced.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.rag.loader import load_file  # noqa: E402
from app.rag.store import get_store, list_register  # noqa: E402


def ingest_from_register(store, reset: bool = False, register: Path | None = None) -> int:
    register = register or settings.SOURCE_REGISTER
    if reset:
        for src in list_register():
            store.delete_document(src["doc_id"])
    total = 0
    with open(register, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            path = register.parent / row["file"]
            doc = load_file(path, metadata={k: v for k, v in row.items() if k != "file"})
            n = store.index_document(doc)
            total += n
            m = doc.metadata
            print(f"  {m.doc_id:<20} L{m.authority_level} {m.doc_type:<10} v{m.version:<5} "
                  f"from={m.effective_from or '-':<10} to={m.effective_to or '-':<10} "
                  f"supersedes={';'.join(m.supersedes) or '-':<22} chunks={n:>3}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="a single .md/.txt/.pdf to ingest (default: the whole register)")
    ap.add_argument("--metadata", default=None, help="JSON metadata for a single file")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    store = get_store()
    if args.path:
        doc = load_file(Path(args.path), metadata=json.loads(args.metadata) if args.metadata else None)
        n = store.index_document(doc)
        print(f"{doc.metadata.doc_id}: {n} chunks")
    else:
        total = ingest_from_register(store, reset=args.reset)
        print(f"\n{len(list_register())} documents in the register, {total} chunks indexed this run, "
              f"{store.count()} chunks in the store.")


if __name__ == "__main__":
    main()
