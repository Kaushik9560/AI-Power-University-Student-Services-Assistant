"""Persistent Chroma index and SQLite-backed source register."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.rag.chunker import chunk_document
from app.rag.embeddings import get_embedding_function
from app.rag.loader import DocumentMetadata, LoadedDocument

log = logging.getLogger(__name__)

_REGISTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_register (
    doc_id TEXT PRIMARY KEY,
    metadata TEXT NOT NULL,
    chunks INTEGER NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@contextmanager
def _register_connection():
    path = Path(get_settings().source_register_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(_REGISTER_SCHEMA)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def upsert_register(metadata: DocumentMetadata, chunks: int) -> None:
    with _register_connection() as connection:
        connection.execute(
            "INSERT INTO source_register (doc_id, metadata, chunks) VALUES (?, ?, ?) "
            "ON CONFLICT(doc_id) DO UPDATE SET metadata=excluded.metadata, "
            "chunks=excluded.chunks, indexed_at=CURRENT_TIMESTAMP",
            (metadata.doc_id, json.dumps(metadata.as_dict()), chunks),
        )


def list_register() -> list[dict[str, Any]]:
    with _register_connection() as connection:
        rows = connection.execute(
            "SELECT metadata, chunks, indexed_at FROM source_register "
            "ORDER BY json_extract(metadata, '$.authority_level'), doc_id"
        ).fetchall()
    return [{**json.loads(row["metadata"]), "chunks": row["chunks"], "indexed_at": row["indexed_at"]}
            for row in rows]


class VectorStore:
    def __init__(self) -> None:
        import chromadb

        settings = get_settings()
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=settings.chroma_path)
        self._collection = client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        self._embed = get_embedding_function()
        self._lock = threading.RLock()

    def delete_document(self, doc_id: str) -> None:
        with self._lock:
            existing = self._collection.get(where={"doc_id": doc_id}, include=[])
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
            with _register_connection() as connection:
                connection.execute("DELETE FROM source_register WHERE doc_id = ?", (doc_id,))

    def index_document(self, document: LoadedDocument) -> int:
        settings = get_settings()
        chunks = chunk_document(
            document.metadata.doc_id,
            document.pages,
            size=settings.chunk_size_chars,
            overlap=settings.chunk_overlap_chars,
        )
        if not chunks:
            raise ValueError(f"Document {document.metadata.doc_id} contains no indexable text")

        metadata = document.metadata.as_dict()
        chroma_metadata = {
            key: ";".join(value) if isinstance(value, (list, tuple)) else value
            for key, value in metadata.items()
            if value is not None
        }
        with self._lock:
            existing = self._collection.get(where={"doc_id": document.metadata.doc_id}, include=[])
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
            self._collection.add(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {**chroma_metadata, "section": chunk.section, "clause": chunk.clause,
                     "page": chunk.page if chunk.page is not None else -1, "position": chunk.position}
                    for chunk in chunks
                ],
                embeddings=self._embed([chunk.text for chunk in chunks]),
            )
            upsert_register(document.metadata, len(chunks))
        log.info("Indexed %s as %d chunks", document.metadata.doc_id, len(chunks))
        return len(chunks)

    def query(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        settings = get_settings()
        count = self._collection.count()
        if not query.strip() or count == 0:
            return []
        top_k = limit or settings.retrieval_top_k
        result = self._collection.query(
            query_embeddings=self._embed([query]),
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            item = dict(metadata)
            page = item.get("page")
            item.update({
                "chunk_id": chunk_id,
                "text": text,
                "page": None if page in (None, -1) else int(page),
                "distance": float(distance),
                "score": round(max(0.0, min(1.0, 1.0 - float(distance))), 3),
            })
            chunks.append(item)
        return chunks

    def count(self) -> int:
        return self._collection.count()

    def health(self) -> dict[str, Any]:
        try:
            return {"status": "ok", "chunks": self.count(), "documents": len(list_register())}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)[:120]}


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def search(query: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Return the most relevant chunks with their source metadata."""
    return get_store().query(query, limit)
