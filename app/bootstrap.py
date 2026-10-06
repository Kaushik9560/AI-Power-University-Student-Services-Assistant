"""Load missing demo data once; reuse the persisted index on subsequent starts."""
from __future__ import annotations

import csv
import logging

from app.config import settings
from app.db.database import init_schema, load_csv_tables, table_counts
from app.rag.loader import load_file
from app.rag.store import list_register

log = logging.getLogger(__name__)


def ensure_local_data(store) -> dict:
    init_schema()
    counts = table_counts()
    if not counts["students"]:
        from scripts.validate_students import validate

        errors, _ = validate(settings.SYNTHETIC_DIR)
        if errors:
            raise ValueError(f"Invalid synthetic student kit: {errors[0]}")
        load_csv_tables({table: settings.SYNTHETIC_DIR / f"{table}.csv"
                         for table in ("students", "courses", "attendance", "results")})
    # Add only absent baseline rules. Never overwrite judges' or newly ingested rules.
    if not counts["rule_registry"] and settings.RULE_REGISTRY_PATH.is_file():
        load_csv_tables({"rule_registry": settings.RULE_REGISTRY_PATH})
    indexed = []
    registered = {row["doc_id"] for row in list_register()}
    with settings.SOURCE_REGISTER.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row["doc_id"] in registered and store.document_count(row["doc_id"]):
                continue
            path = settings.SOURCE_REGISTER.parent / row["file"]
            document = load_file(path, {key: value for key, value in row.items() if key != "file"})
            if not document.text.strip():
                raise ValueError(f"No extractable policy text in {path.name}")
            store.index_document(document)
            indexed.append(row["doc_id"])
    if not store.count():
        raise ValueError("Policy index is empty; check SOURCE_REGISTER and CHROMA_COLLECTION")
    log.info("Profile ready: %s; indexed missing documents: %s", settings.SOURCE_REGISTER, indexed)
    return {"indexed": indexed, "chunks": store.count()}
