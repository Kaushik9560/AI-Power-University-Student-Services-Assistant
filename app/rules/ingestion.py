"""Extract explicit numeric attendance amendments; never infer thresholds with an LLM."""
from __future__ import annotations

import hashlib
import re

from app.db.database import get_connection

_MINIMUM = re.compile(
    r"(?:minimum\s+attendance(?:\s+(?:required|requirement|threshold))?|attendance\s+(?:requirement|threshold))"
    r"\s*(?:is|of|shall\s+be|must\s+be|:|=|at\s+least|revised\s+to)?\s*(\d+(?:\.\d+)?)\s*(?:%|percent|per\s+cent)", re.I)


def sync_document_rules(document, chunks) -> list[str]:
    """Register unambiguous, explicit minimum-attendance clauses from level 1/2 sources.

    Other policies need reviewed rule-registry rows. Quoted instructions, relaxations,
    conflicting values inside one clause and lower-authority notes never become rules.
    """
    meta = document.metadata
    rows = []
    if meta.authority_level <= 2:
        for chunk in chunks:
            values = set(_MINIMUM.findall(chunk.text))
            if len(values) != 1:
                continue
            value = values.pop()
            if not 0 <= float(value) <= 100:
                continue
            if re.search(r"ignore\s+(?:previous|all)|system\s+prompt|assistant\s*:", chunk.text, re.I):
                continue
            section = chunk.clause or chunk.section
            key = f"{meta.doc_id}|{section}|min_attendance_pct"
            rule_id = "AUTO-" + hashlib.sha256(key.encode()).hexdigest()[:20]
            rows.append((rule_id, "Minimum attendance explicitly stated in the cited clause",
                         "min_attendance_pct", ">=", value,
                         ";".join(meta.scope_programmes) or "ALL", meta.scope_batches,
                         meta.effective_from, meta.effective_to, meta.doc_id, section))
    with get_connection() as connection:
        connection.execute("DELETE FROM rule_registry WHERE source_doc_id = ? AND rule_id LIKE 'AUTO-%'", (meta.doc_id,))
        connection.executemany("INSERT OR REPLACE INTO rule_registry VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    return [row[0] for row in rows]
