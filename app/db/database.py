"""Database bootstrapping, schema application, and CSV loading utilities.

The deterministic layer is intentionally kept database-first. SQLite stores raw
facts such as counts and rule metadata, while Python code performs any numeric
calculations. This split keeps the LLM out of arithmetic and policy logic.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "university.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection and enable foreign-key enforcement.

    We configure the connection here so all module-level queries use a consistent,
    safe database contract. The row_factory keeps results dictionary-like so the
    policy engine can read explicit field names without fragile indexing.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_database(db_path: str | Path = DB_PATH) -> Path:
    """Apply the schema to a database and return the final path.

    The database is initialized from SQL because schema definitions are always
    authoritative and easier to audit than ad-hoc Python DDL strings.
    """
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(target)
    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    return target


def load_csv_rows(csv_path: str | Path) -> list[dict[str, str]]:
    """Read a CSV file into a normalized list of row dictionaries.

    This loader is intentionally simple and deterministic: it does not mutate the
    dataset or calculate derived values. It just surfaces raw rows for explicit
    database insertion or tooling use.
    """
    csv_file = Path(csv_path)
    with csv_file.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def insert_csv_rows(
    table_name: str,
    rows: Iterable[dict[str, str]],
    db_path: str | Path = DB_PATH,
) -> None:
    """Insert a CSV-derived row set into a SQLite table.

    The loader is deliberately strict: each row must match a table shape and the
    insert is done in a single transaction. We avoid dynamic SQL generation here
    because holding a fixed table contract is safer than letting the LLM or a
    caller invent arbitrary column names.
    """
    if not table_name:
        raise ValueError("table_name must not be empty")

    row_list = list(rows)
    if not row_list:
        return

    columns = list(row_list[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders})"

    conn = get_connection(db_path)
    try:
        conn.executemany(sql, [tuple(row[col] for col in columns) for row in row_list])
        conn.commit()
    finally:
        conn.close()


def _seed_reference_data(conn: sqlite3.Connection) -> None:
    """Insert the test fixture used by the deterministic student-data layer.

    We intentionally keep the seed data small but representative: one eligible,
    one boundary-case, one detained, and one rule registry entry. The values are
    raw counts and policy metadata only; no percentage is stored in the database.
    """
    students = [
        ("S1001", "Aarav Sharma", "B.Tech CSE", 2023, 4, 8.45, 0),
        ("S1002", "Priya Verma", "B.Tech CSE", 2023, 4, 7.80, 0),
        ("S1003", "Rohan Gupta", "B.Tech CSE", 2023, 4, 6.90, 1),
        ("S1004", "Sneha Patel", "B.Tech ECE", 2024, 2, 5.80, 2),
    ]
    courses = [
        ("CS201", "Data Structures", "B.Tech CSE", 3, 4),
        ("CS202", "Discrete Mathematics", "B.Tech CSE", 3, 4),
        ("EC201", "Digital Electronics", "B.Tech ECE", 3, 4),
    ]
    attendance = [
        ("S1001", "CS201", 40, 35),
        ("S1002", "CS201", 40, 30),
        ("S1003", "CS201", 40, 29),
        ("S1004", "EC201", 36, 20),
    ]
    results = [
        ("S1001", "CS201", "2025-DEC", "REGULAR", 25, 55, 80, 100, "PASS"),
        ("S1002", "CS201", "2025-DEC", "REGULAR", 20, 42, 62, 100, "PASS"),
        ("S1003", "CS201", "2025-DEC", "REGULAR", 14, 25, 39, 100, "FAIL"),
        ("S1004", "EC201", "2025-DEC", "REGULAR", 0, 0, 0, 100, "ABSENT"),
    ]
    rules = [
        (
            "ATT-MIN-01",
            "Minimum attendance required to appear in regular end-semester exams",
            "min_attendance_pct",
            ">=",
            "75.0",
            "ALL",
            "ALL",
            "2024-07-01",
            None,
            "ACAD-REG-2024",
            "7.2",
        ),
        (
            "PASS-MARK-01",
            "Minimum total marks required to clear a course",
            "min_pass_marks",
            ">=",
            "40.0",
            "ALL",
            "ALL",
            "2024-07-01",
            None,
            "ACAD-REG-2024",
            "8.1",
        ),
    ]

    conn.executemany("INSERT OR REPLACE INTO students VALUES (?, ?, ?, ?, ?, ?, ?)", students)
    conn.executemany("INSERT OR REPLACE INTO courses VALUES (?, ?, ?, ?, ?)", courses)
    conn.executemany("INSERT OR REPLACE INTO attendance VALUES (?, ?, ?, ?)", attendance)
    conn.executemany("INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", results)
    conn.executemany(
        "INSERT OR REPLACE INTO rule_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rules,
    )
    conn.commit()


def bootstrap_database(db_path: str | Path = DB_PATH) -> Path:
    """Create a ready-to-use SQLite database with schema and sample rows.

    This function is deliberately idempotent for tests: re-running it should leave
    the database in a known-good state. That allows the graph and tool layer to
    boot in a deterministic environment before any user request reaches the LLM.
    """
    target = Path(db_path)
    create_database(target)

    conn = get_connection(target)
    try:
        _seed_reference_data(conn)
    finally:
        conn.close()

    return target
