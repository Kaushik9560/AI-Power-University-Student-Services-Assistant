"""Regression tests for document loading, embeddings, and retrieval persistence."""

import csv
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.api import routes
from app.rag.embeddings import get_embedding_function
from app.rag.loader import load_file, parse_markdown
from app.rag.store import VectorStore, list_register


def test_markdown_front_matter_and_tolerant_fallback() -> None:
    document = parse_markdown(
        "---\ndoc_id: ATTENDANCE\ntitle: Attendance Policy\nauthority_level: 1\n"
        "effective_from: 2026-01-01\nsupersedes: OLD#7.2\n---\n# Attendance\n75 percent required.",
        "fallback",
    )

    assert document.metadata.doc_id == "ATTENDANCE"
    assert document.metadata.authority_level == 1
    assert document.metadata.effective_from == "2026-01-01"
    assert document.metadata.supersedes == ("OLD#7.2",)
    assert "75 percent required" in document.text

    tolerant = parse_markdown("---\ndoc_id: SIMPLE\ntitle: unquoted: value\n---\nBody", "fallback")
    assert tolerant.metadata.doc_id == "SIMPLE"
    assert tolerant.text == "Body"


def test_hash_embeddings_are_normalized_and_repeatable() -> None:
    embed = get_embedding_function("hash")
    vectors = embed(["Attendance requirement", "Attendance requirement", ""])

    assert vectors[0] == vectors[1]
    assert len(vectors[0]) == 512
    assert sum(value * value for value in vectors[0]) == pytest.approx(1.0)
    assert vectors[2] == [0.0] * 512


def test_store_reingestion_query_and_delete(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("SOURCE_REGISTER_DB", str(tmp_path / "sources.db"))
    monkeypatch.setenv("CHROMA_COLLECTION", "rag_test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("CHUNK_SIZE_CHARS", "900")
    monkeypatch.setenv("CHUNK_OVERLAP_CHARS", "150")
    get_settings.cache_clear()
    try:
        store = VectorStore()
        document = parse_markdown(
            "---\ndoc_id: ATTENDANCE\ntitle: Attendance Policy\nauthority_level: 1\n---\n"
            "# Attendance\nStudents need 75 percent attendance.",
            "fallback",
        )

        assert store.index_document(document) == 1
        assert store.index_document(document) == 1
        assert store.count() == 1
        results = store.query("attendance minimum", limit=1)
        assert results[0]["doc_id"] == "ATTENDANCE"
        assert results[0]["clause"] == ""
        assert list_register()[0]["chunks"] == 1

        store.delete_document("ATTENDANCE")
        assert store.count() == 0
        assert list_register() == []
    finally:
        get_settings.cache_clear()


def test_bulk_ingest_rejects_paths_outside_register_directory(tmp_path, monkeypatch) -> None:
    from scripts.ingest_documents import ingest_documents

    register = tmp_path / "source_register.csv"
    with register.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["doc_id", "file"])
        writer.writeheader()
        writer.writerow({"doc_id": "ESCAPE", "file": "../outside.txt"})
    (tmp_path.parent / "outside.txt").write_text("not an allowed source", encoding="utf-8")
    monkeypatch.setenv("SOURCE_REGISTER", str(register))
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="escapes"):
            ingest_documents()
    finally:
        get_settings.cache_clear()


def test_file_loader_rejects_unknown_suffix(tmp_path) -> None:
    unknown = tmp_path / "source.csv"
    unknown.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported document type"):
        load_file(unknown)


def test_live_ingest_upload_indexes_document(monkeypatch) -> None:
    class FakeStore:
        def index_document(self, document):
            assert document.metadata.doc_id == "LIVE-POLICY"
            assert "75 percent" in document.text
            return 2

    monkeypatch.setattr(routes, "get_store", lambda: FakeStore())
    monkeypatch.setattr(routes, "list_register", lambda: [{"doc_id": "LIVE-POLICY"}])
    application = FastAPI()
    application.include_router(routes.router)
    client = TestClient(application)
    response = client.post(
        "/ingest",
        files={"file": ("attendance.md", b"# Attendance\n75 percent required.", "text/markdown")},
        data={"metadata": json.dumps({"doc_id": "LIVE-POLICY", "authority_level": 1})},
    )

    assert response.status_code == 200
    assert response.json() == {
        "doc_id": "LIVE-POLICY", "chunks_indexed": 2, "status": "indexed",
        "title": "attendance", "total_documents": 1,
    }