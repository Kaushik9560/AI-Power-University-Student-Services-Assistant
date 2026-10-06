"""SQLite helpers. One file (data/university.db) holds student data, rule registry and source register."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from app.config import settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
TABLES = ("students", "courses", "attendance", "results", "rule_registry")
LOAD_ORDER = ("courses", "students", "attendance", "results", "rule_registry")


def get_connection() -> sqlite3.Connection:
    settings.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


def load_csv_table(table: str, csv_path: Path, replace: bool = False) -> int:
    """Upsert rows from a CSV whose header matches the table columns (extra columns ignored)."""
    return load_csv_tables({table: csv_path}, replace=replace)[table]


def load_csv_tables(paths: dict[str, Path], replace: bool = False) -> dict[str, int]:
    """Load a batch atomically, clearing child tables before parents when replacing."""
    unknown = set(paths) - set(TABLES)
    if unknown:
        raise ValueError(f"unknown tables {sorted(unknown)}")
    init_schema()
    with get_connection() as conn:
        prepared = {}
        for table in LOAD_ORDER:
            if table not in paths:
                continue
            schema = conn.execute(f"PRAGMA table_info({table})").fetchall()
            cols = [r[1] for r in schema]
            updates = [f"{r[1]} = excluded.{r[1]}" for r in schema if not r[5]]
            with open(paths[table], newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                missing = [c for c in cols if c not in (reader.fieldnames or [])]
                if missing and table != "rule_registry":
                    raise ValueError(f"{paths[table].name} is missing columns {missing}")
                rows = [[r.get(c) if r.get(c) not in ("", None) else None for c in cols] for r in reader]
            prepared[table] = (cols, updates, rows)
        if replace:
            for table in reversed(prepared):
                conn.execute(f"DELETE FROM {table}")
        for table, (cols, updates, rows) in prepared.items():
            # INSERT OR REPLACE deletes the parent row and breaks existing foreign keys.
            conn.executemany(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                f"ON CONFLICT DO UPDATE SET {', '.join(updates)}", rows)
    return {table: len(rows) for table, (_, _, rows) in prepared.items()}


def table_counts() -> dict[str, int]:
    with get_connection() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {t: (conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in names else 0) for t in TABLES}


def sqlite_health() -> dict:
    try:
        counts = table_counts()
        return {"status": "ok" if counts["students"] else "empty", "path": str(settings.SQLITE_PATH), **counts}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)[:120]}
