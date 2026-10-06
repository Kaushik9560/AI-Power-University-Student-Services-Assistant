"""Offline test setup: hash embeddings, mock LLM, fake Chroma, temp SQLite with the synthetic data."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "tests" / "_tmp"
TMP.mkdir(exist_ok=True)
os.environ.update({
    "EMBEDDING_PROVIDER": "hash", "MOCK_LLM": "true", "LLM_PROVIDER": "mock",
    "RETRIEVAL_MAX_DISTANCE": "0.95",            # hash embeddings are weak; tests check logic, not ranking
    "RETRIEVAL_TOP_K": "12",
    "SQLITE_PATH": str(TMP / "university.db"), "AUDIT_DB_PATH": str(TMP / "audit.db"),
    "SOURCE_REGISTER": str(ROOT / "data" / "source_register.csv"),
    "DOCUMENTS_DIR": str(ROOT / "data" / "documents"),
    "SYNTHETIC_DIR": str(ROOT / "data" / "synthetic"),
    "RULE_REGISTRY_PATH": str(ROOT / "data" / "synthetic" / "rule_registry.csv"),
})
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    from app.db.database import init_schema, load_csv_table
    from app.config import settings

    for p in (TMP / "university.db", TMP / "audit.db"):
        p.unlink(missing_ok=True)
    init_schema()
    for t in ("courses", "students", "attendance", "results", "rule_registry"):
        load_csv_table(t, settings.SYNTHETIC_DIR / f"{t}.csv", replace=True)
    yield


@pytest.fixture(autouse=True)
def fake_store(monkeypatch):
    import app.rag.store as store_mod
    from tests.fake_store import FakeStore

    if getattr(store_mod, "_store", None) is None or not isinstance(store_mod._store, FakeStore):
        store_mod._store = FakeStore()
    return store_mod._store


@pytest.fixture
def ask():
    from app.graph.workflow import run_query_without_langgraph

    def _ask(question: str, student_id: str | None = "S1001", as_of: str = "2026-10-06") -> dict:
        return run_query_without_langgraph(question, student_id, as_of)

    return _ask
