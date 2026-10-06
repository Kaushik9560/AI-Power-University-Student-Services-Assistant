"""
Vector store (ChromaDB persisted to disk — not re-ingested on restart) plus the
Source Register (SQLite table) that GET /sources reads.

index_document() is the single write path used by scripts/ingest_documents.py and
POST /ingest, so a document ingested live is searchable immediately. Re-ingesting a
doc_id replaces its chunks (idempotent).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.db.database import get_connection
from app.rag.chunker import chunk_document
from app.rag.embeddings import get_embed_fn
from app.rag.loader import DocumentMetadata, LoadedDocument
from app.rag.ranking import rerank_chunks

log = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    section: str
    clause: str
    page: int | None
    distance: float
    metadata: DocumentMetadata
    relevance_score: float | None = None

    @property
    def doc_id(self) -> str:
        return self.metadata.doc_id

    @property
    def score(self) -> float:
        """Similarity in [0,1] for audit records (1 - cosine distance, clipped)."""
        return round(max(0.0, min(1.0, 1.0 - self.distance)), 3)

    @property
    def rank_score(self) -> float:
        return self.relevance_score if self.relevance_score is not None else 1.0 - self.distance

    def to_dict(self) -> dict[str, Any]:
        m = self.metadata
        return {
            "chunk_id": self.chunk_id, "doc_id": m.doc_id, "title": m.title, "issuer": m.issuer,
            "section": self.section, "clause": self.clause, "page": self.page,
            "version": m.version, "effective_from": m.effective_from, "effective_to": m.effective_to,
            "authority_level": m.authority_level, "doc_type": m.doc_type, "supersedes": m.supersedes,
            "scope_programmes": m.scope_programmes, "scope_batches": m.scope_batches,
            "score": self.score, "text": self.text,
        }


class VectorStore:
    def __init__(self):
        import chromadb

        settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})
        self._embed = get_embed_fn()
        self._lock = threading.Lock()

    # ---- write ---------------------------------------------------------
    def index_document(self, doc: LoadedDocument) -> int:
        chunks = chunk_document(doc.metadata.doc_id, doc.pages)
        base = doc.metadata.to_chroma()
        with self._lock:
            self.delete_document(doc.metadata.doc_id)
            if chunks:
                self._collection.add(
                    ids=[c.chunk_id for c in chunks],
                    documents=[c.text for c in chunks],
                    metadatas=[{**base, "section": c.section, "clause": c.clause,
                                "page": c.page if c.page is not None else -1, "position": c.position}
                               for c in chunks],
                    embeddings=self._embed([c.text for c in chunks]),
                )
            upsert_register(doc.metadata, len(chunks))
            from app.rules.ingestion import sync_document_rules
            sync_document_rules(doc, chunks)
        log.info("Indexed %s (%d chunks)", doc.metadata.doc_id, len(chunks))
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        try:
            existing = self._collection.get(where={"doc_id": doc_id}, include=[])
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:  # noqa: BLE001
            pass

    # ---- read ----------------------------------------------------------
    def query(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        n = self._collection.count()
        if n == 0:
            return []
        res = self._collection.query(query_embeddings=self._embed([question]), n_results=min(top_k * 4, n),
                                     include=["documents", "metadatas", "distances"])
        out = []
        for cid, text, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            page = meta.get("page")
            out.append(RetrievedChunk(
                chunk_id=cid, text=text, section=meta.get("section", ""), clause=meta.get("clause", ""),
                page=None if page in (None, -1) else int(page), distance=float(dist),
                metadata=DocumentMetadata.from_row(meta)))
        return rerank_chunks(question, out)[:top_k]

    def count(self) -> int:
        return self._collection.count()

    def document_count(self, doc_id: str) -> int:
        return len(self._collection.get(where={"doc_id": doc_id}, include=[])["ids"])

    def lookup_clause(self, doc_id: str, clause: str) -> dict | None:
        result = self._collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
        for cid, text, meta in zip(result["ids"], result["documents"], result["metadatas"]):
            if str(meta.get("clause", "")) == clause:
                return RetrievedChunk(cid, text, meta.get("section", ""), clause,
                                      None if meta.get("page", -1) == -1 else int(meta["page"]),
                                      0.0, DocumentMetadata.from_row(meta)).to_dict()
        return None

    def health(self) -> dict:
        try:
            count = self.count()
            return {"status": "ok" if count else "empty", "chunks": count,
                    "documents": len(list_register()), "path": str(settings.CHROMA_DIR),
                    "collection": settings.CHROMA_COLLECTION}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)[:120]}


# --------------------------------------------------------------------------
# Source Register (SQLite). Same fields as Annex B plus chunk count.
# --------------------------------------------------------------------------
_REGISTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_register (
    doc_id TEXT PRIMARY KEY, title TEXT, issuer TEXT, authority_level INTEGER, doc_type TEXT,
    version TEXT, effective_from TEXT, effective_to TEXT, supersedes TEXT, scope_programmes TEXT,
    scope_batches TEXT, provenance TEXT, retrieved_on TEXT, synthetic TEXT,
    chunks INTEGER DEFAULT 0, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def upsert_register(meta: DocumentMetadata, chunks: int) -> None:
    row = meta.to_register_row()
    row["chunks"] = chunks
    with get_connection() as conn:
        conn.execute(_REGISTER_SCHEMA)
        cols = ", ".join(row)
        conn.execute(f"INSERT OR REPLACE INTO source_register ({cols}, ingested_at) "
                     f"VALUES ({', '.join('?' * len(row))}, CURRENT_TIMESTAMP)", list(row.values()))


def list_register() -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.execute(_REGISTER_SCHEMA)
        rows = conn.execute("SELECT * FROM source_register ORDER BY authority_level, effective_from DESC, doc_id").fetchall()
    return [dict(r) for r in rows]


def register_doc_ids() -> set[str]:
    return {r["doc_id"] for r in list_register()}


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
