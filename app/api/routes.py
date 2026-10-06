"""Shared API routes. Announce contract changes before editing."""

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.api.schemas import AskRequest, AskResponse
from app.rag.loader import load_bytes
from app.rag.store import get_store, list_register

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight readiness response."""

    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Accept the stable API shape while area implementations are built."""

    return AskResponse(answer=f"Received: {request.question}")


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...), metadata: str = Form(default="{}")) -> dict:
    """Index an uploaded Markdown, text, or PDF document immediately."""
    try:
        source_metadata = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc
    if not isinstance(source_metadata, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    if not file.filename:
        raise HTTPException(status_code=400, detail="uploaded file must have a filename")
    try:
        document = load_bytes(file.filename, await file.read(), source_metadata)
        if not document.text.strip():
            raise ValueError("document contains no extractable text")
        chunks = get_store().index_document(document)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"doc_id": document.metadata.doc_id, "chunks_indexed": chunks, "status": "indexed",
            "title": document.metadata.title, "total_documents": len(list_register())}


@router.get("/sources")
def sources() -> list[dict]:
    """List source metadata and indexed chunk counts."""
    return list_register()
