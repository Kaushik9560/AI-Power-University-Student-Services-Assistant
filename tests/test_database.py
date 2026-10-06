"""Regression checks for repeat loads with existing foreign-key references."""
import csv
import sqlite3

import pytest

from app.config import settings
from app.db.database import LOAD_ORDER, get_connection, load_csv_table, load_csv_tables, table_counts


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_PATH", tmp_path / "students.db")
    paths = {table: settings.SYNTHETIC_DIR / f"{table}.csv" for table in LOAD_ORDER}
    load_csv_tables(paths, replace=True)
    return paths


def test_full_replacement_can_run_twice(seeded_db):
    before = table_counts()
    load_csv_tables(seeded_db, replace=True)
    assert table_counts() == before
    assert before["students"] == 32 and before["attendance"] == 144
    with get_connection() as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_updating_parent_preserves_student_records(seeded_db, tmp_path):
    with seeded_db["students"].open() as f:
        row = next(csv.DictReader(f))
    row["cgpa"] = "9.0"
    updated = tmp_path / "students.csv"
    with updated.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    assert load_csv_table("students", updated) == 1
    with get_connection() as conn:
        assert conn.execute("SELECT cgpa FROM students WHERE student_id = ?", (row["student_id"],)).fetchone()[0] == 9.0
    assert table_counts()["attendance"] == 144
    assert table_counts()["results"] == 97


def test_failed_replacement_rolls_back_all_tables(seeded_db, tmp_path):
    before = table_counts()
    with seeded_db["attendance"].open() as f:
        row = next(csv.DictReader(f))
    row["classes_held"] = "0"
    invalid = tmp_path / "attendance.csv"
    with invalid.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(sqlite3.IntegrityError):
        load_csv_tables({**seeded_db, "attendance": invalid}, replace=True)
    assert table_counts() == before
