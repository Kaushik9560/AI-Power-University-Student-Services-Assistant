"""OWNER: student-data. TODO step 2: manage database connections and schema setup."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Yield a row-aware SQLite connection."""

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()
