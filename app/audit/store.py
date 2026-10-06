"""
Audit log (guide R10 / Annex D). SQLite table in data/audit.db — one row per /ask.
Operational facts only: no chain-of-thought, no personal data beyond the student id and
the tool inputs/outputs needed to reproduce the answer.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    trace_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, student_id TEXT, question TEXT NOT NULL,
    as_of_date TEXT, question_category TEXT, query_type TEXT, answer_type TEXT,
    sources_retrieved TEXT, sources_used TEXT, sources_dropped TEXT, precedence_decision TEXT,
    tools_invoked TEXT, rules_applied TEXT, conflicts_detected TEXT, assumptions TEXT,
    model TEXT, llm_calls INTEGER, tokens INTEGER, latency_ms INTEGER, errors TEXT, tool_plan TEXT,
    original_question TEXT, previous_trace_id TEXT
);
"""
_JSON = ("sources_retrieved", "sources_used", "sources_dropped", "tools_invoked", "rules_applied",
         "conflicts_detected", "assumptions", "errors", "tool_plan")


def _connect() -> sqlite3.Connection:
    settings.AUDIT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.AUDIT_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
    for name, definition in (("tool_plan", "TEXT DEFAULT '{}'"), ("original_question", "TEXT"),
                             ("previous_trace_id", "TEXT")):
        if name not in columns:
            conn.execute(f"ALTER TABLE audit_log ADD COLUMN {name} {definition}")
    conn.commit()
    return conn


def build_record(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_id": state["trace_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "student_id": state.get("student_id"),
        "question": state["question"],
        "original_question": state.get("original_question", state["question"]),
        "previous_trace_id": state.get("previous_trace_id"),
        "as_of_date": state.get("as_of_date"),
        "question_category": state.get("question_category"),
        "query_type": state.get("query_type"),
        "answer_type": state.get("answer_type"),
        "sources_retrieved": state.get("sources_retrieved", []),
        "sources_used": [{k: c.get(k) for k in ("doc_id", "section", "page", "version", "effective_from")}
                         for c in state.get("citations", [])],
        "sources_dropped": state.get("dropped_sources", []),
        "precedence_decision": state.get("precedence_decision", ""),
        "tools_invoked": [{"tool": t["tool"], "input": t.get("input"), "output": t.get("output"),
                           "status": t["status"], "ms": t["ms"]} for t in state.get("tools_invoked", [])],
        "rules_applied": [r.get("rule_id") for r in state.get("applied_rules", [])],
        "conflicts_detected": state.get("conflicts", []),
        "assumptions": state.get("assumptions", []),
        "model": state.get("model_used"),
        "tool_plan": state.get("tool_plan", {}),
        "llm_calls": state.get("llm_calls", 0),
        "tokens": state.get("tokens", 0),
        "latency_ms": state.get("latency_ms"),
        "errors": state.get("errors", []),
    }


def write_audit(state: dict[str, Any]) -> dict[str, Any]:
    rec = build_record(state)
    row = {k: (json.dumps(v, default=str) if k in _JSON else v) for k, v in rec.items()}
    with _connect() as conn:
        conn.execute(f"INSERT OR REPLACE INTO audit_log ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                     list(row.values()))
    return rec


def read_audit(trace_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM audit_log WHERE trace_id = ?", (trace_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in _JSON:
        d[k] = json.loads(d[k]) if d[k] else []
    return d


def audit_health() -> dict:
    try:
        with _connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        return {"status": "ok", "records": n, "path": str(settings.AUDIT_DB_PATH)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)[:120]}
