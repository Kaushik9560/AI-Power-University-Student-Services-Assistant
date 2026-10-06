"""
Chroma-free vector store with the same interface as app.rag.store.VectorStore, backed by the
hash embedding. Lets the test-suite and the sandbox evaluation run without model downloads.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.config import settings
from app.rag.chunker import chunk_document
from app.rag.embeddings import _hash_embed
from app.rag.loader import LoadedDocument, load_file
from app.rag.store import RetrievedChunk, upsert_register


def load_register_docs() -> list[LoadedDocument]:
    docs = []
    with open(settings.SOURCE_REGISTER, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            path = settings.SOURCE_REGISTER.parent / row["file"]
            docs.append(load_file(path, metadata={k: v for k, v in row.items() if k != "file"}))
    return docs


class FakeStore:
    def __init__(self, docs: list[LoadedDocument] | None = None):
        self.items: list = []
        self.vecs: list = []
        for d in docs if docs is not None else load_register_docs():
            self.index_document(d)

    def index_document(self, doc: LoadedDocument) -> int:
        self.delete_document(doc.metadata.doc_id)
        chunks = chunk_document(doc.metadata.doc_id, doc.pages)
        self.items += [(c, doc.metadata) for c in chunks]
        self.vecs += _hash_embed([c.text for c in chunks])
        upsert_register(doc.metadata, len(chunks))
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        keep = [(i, v) for i, v in zip(self.items, self.vecs) if i[1].doc_id != doc_id]
        self.items, self.vecs = [k[0] for k in keep], [k[1] for k in keep]

    def query(self, q: str, top_k: int = 8) -> list[RetrievedChunk]:
        qv = _hash_embed([q])[0]
        scored = []
        for (c, m), v in zip(self.items, self.vecs):
            sim = sum(a * b for a, b in zip(qv, v))
            scored.append(RetrievedChunk(c.chunk_id, c.text, c.section, c.clause, c.page, 1 - sim, m))
        scored.sort(key=lambda r: r.distance)
        return scored[:top_k]

    def count(self) -> int:
        return len(self.items)

    def document_count(self, doc_id: str) -> int:
        return sum(metadata.doc_id == doc_id for _, metadata in self.items)

    def health(self) -> dict:
        return {"status": "ok", "chunks": self.count()}
