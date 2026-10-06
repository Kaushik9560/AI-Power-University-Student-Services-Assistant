from datetime import date

import pytest

from app.bootstrap import ensure_local_data
from app.config import settings
from app.db.database import LOAD_ORDER, init_schema, load_csv_tables, table_counts
from app.rag.chunker import chunk_document
from app.rag.loader import DocumentMetadata, LoadedDocument
from app.rules.eligibility import RuleError, get_applicable_rule
from app.rules.ingestion import sync_document_rules
from tests.fake_store import FakeStore


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_PATH", tmp_path / "demo.db")
    init_schema()
    return FakeStore(docs=[])


def test_first_start_loads_data_and_second_start_reuses_index(isolated, monkeypatch):
    first = ensure_local_data(isolated)
    assert first["indexed"] and first["chunks"] > 0
    assert table_counts()["students"] == 32
    monkeypatch.setattr(isolated, "index_document", lambda _: pytest.fail("Existing index was rebuilt"))
    assert ensure_local_data(isolated)["indexed"] == []


def test_missing_document_is_repaired_without_resetting_other_documents(isolated):
    ensure_local_data(isolated)
    isolated.delete_document("ACAD-REG-2024")
    assert ensure_local_data(isolated)["indexed"] == ["ACAD-REG-2024"]


def amendment(store, identifier, percent, level=2):
    metadata = DocumentMetadata(identifier, identifier, authority_level=level, effective_from="2026-10-06",
                                supersedes=["ACAD-REG-2024#7.2", "CIR-ACAD-2026-03#2.1"])
    doc = LoadedDocument(metadata, [(None, f"1.1 The minimum attendance required is {percent} percent to appear for end-semester exams.")])
    store.index_document(doc)
    return sync_document_rules(doc, chunk_document(identifier, doc.pages))


def test_live_amendment_changes_registry_and_equal_priority_conflict_abstains(isolated):
    load_csv_tables({table: settings.SYNTHETIC_DIR / f"{table}.csv" for table in LOAD_ORDER})
    # Populate the original source metadata in this isolated database.
    store = FakeStore()
    assert amendment(store, "LIVE-A", 90)
    rule = get_applicable_rule("min_attendance_pct", "B.Tech CSE", 2024, date(2026, 10, 6))
    assert rule["value"] == "90" and rule["source_doc_id"] == "LIVE-A"
    assert amendment(store, "LIVE-B", 85)
    with pytest.raises(RuleError, match="Conflicting"):
        get_applicable_rule("min_attendance_pct", "B.Tech CSE", 2024, date(2026, 10, 6))


def test_untrusted_note_cannot_register_authoritative_threshold(isolated):
    assert amendment(isolated, "UNTRUSTED", 10, level=5) == []


def test_attendance_what_if_is_computed_and_does_not_change_record(ask):
    from app.tools.student_tools import get_attendance
    before = get_attendance("S1006", "CS301")
    result = ask("If I attend the next 5 classes, will I be eligible for the end-semester exam in DBMS?", "S1006")
    assert result["answer_type"] == "calculated" and result["verdict"] is True
    assert "80.0%" in result["explanation"] and result["assumptions"]
    assert get_attendance("S1006", "CS301") == before


def test_personal_eligibility_requires_header_and_does_not_log_names(ask):
    assert ask("Am I eligible for the end-semester exam in DBMS?", None)["answer_type"] == "refused"
    result = ask("What is my CGPA?", "S1001")
    assert "full_name" not in result["tools_invoked"][0]["output"]
