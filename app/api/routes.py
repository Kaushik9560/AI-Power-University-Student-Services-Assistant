"""HTTP routes — the mandatory contract from guide §6 plus the test-student loader."""
from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.api.schemas import AskRequest, AskResponse, HealthResponse, IngestResponse
from app.audit.store import audit_health, read_audit
from app.db.database import get_connection, load_csv_tables, sqlite_health
from app.graph.workflow import run_query
from app.rag.embeddings import embedding_health
from app.rag.loader import load_bytes
from app.rag.store import get_store, list_register
from app.services.llm import get_llm
from app.services.conversation import continue_clarification

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ask", response_model=AskResponse, response_model_exclude_none=False)
def ask(req: AskRequest, x_student_id: Optional[str] = Header(default=None, alias="X-Student-Id")) -> AskResponse:
    # R7: identity comes ONLY from the header, never from the message text.
    student_id = x_student_id.strip().upper() if x_student_id and x_student_id.strip() else None
    as_of = req.as_of_date or date.today().isoformat()
    question = req.question
    if req.previous_trace_id:
        previous = read_audit(req.previous_trace_id)
        if not previous:
            raise HTTPException(status_code=404, detail="Previous response was not found; start a new conversation")
        if previous.get("student_id") != student_id:
            raise HTTPException(status_code=403, detail="Conversation context belongs to a different account")
        if previous.get("as_of_date") != as_of:
            raise HTTPException(status_code=400, detail="Policy date changed; start a new conversation")
        question = continue_clarification(question, previous)
        if len(question) > 2000:
            raise HTTPException(status_code=400, detail="Conversation context is too long; restate the full question")
    s = run_query(question, student_id, as_of, original_question=req.question,
                  previous_trace_id=req.previous_trace_id)
    return AskResponse(
        trace_id=s["trace_id"], answer=s["answer"], answer_type=s["answer_type"],
        citations=s.get("citations", []), tools_invoked=s.get("tools_invoked", []),
        applied_rules=s.get("applied_rules", []), conflicts_detected=s.get("conflicts", []),
        explanation=s.get("explanation", ""), as_of_date=s["as_of_date"], verdict=s.get("verdict"),
        assumptions=s.get("assumptions", []), upcoming_changes=s.get("upcoming_changes", []),
        query_type=s.get("query_type"), latency_ms=s.get("latency_ms"),
        clarification_options=s.get("clarification_options", []),
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...), metadata: str = Form(default="{}")) -> IngestResponse:
    """
    Multipart: `file` (.md/.txt/.pdf) + `metadata` (JSON string with the Source Register fields,
    Annex B). The document is searchable as soon as this call returns.
    """
    try:
        meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"metadata is not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    data = await file.read()
    try:
        doc = load_bytes(file.filename or "document.txt", data, meta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not doc.text.strip():
        raise HTTPException(status_code=400, detail="document has no extractable text (enable OCR_ENABLED for scans)")
    n = get_store().index_document(doc)
    with get_connection() as connection:
        rules = [row[0] for row in connection.execute(
            "SELECT rule_id FROM rule_registry WHERE source_doc_id = ? AND rule_id LIKE 'AUTO-%'", (doc.metadata.doc_id,))]
    return IngestResponse(doc_id=doc.metadata.doc_id, chunks_indexed=n, status="indexed",
                          title=doc.metadata.title, total_documents=len(list_register()), rules_registered=rules)


@router.get("/sources")
def sources() -> list[dict]:
    """The Source Register: every ingested document and its metadata."""
    return list_register()


@router.get("/audit/{trace_id}")
def audit(trace_id: str) -> dict:
    rec = read_audit(trace_id)
    if not rec:
        raise HTTPException(status_code=404, detail="trace_id not found")
    return rec


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    vs, db, llm = get_store().health(), sqlite_health(), get_llm().health()
    overall = "ok" if vs.get("status") == "ok" and db.get("status") == "ok" and llm.get("status") == "ok" else "degraded"
    return HealthResponse(status=overall, api="ok", vector_store=vs, sqlite=db, llm=llm,
                          embeddings=embedding_health(), audit=audit_health())


@router.post("/admin/load-students")
async def load_students(files: list[UploadFile] = File(...), replace: bool = Form(default=False)) -> dict:
    """
    Admin equivalent of scripts/load_students.py: upload students.csv, courses.csv, attendance.csv,
    results.csv (and optionally rule_registry.csv) in the Annex C schema.
    """
    loaded = {}
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            name = Path(f.filename or "").stem.lower()
            if name not in ("students", "courses", "attendance", "results", "rule_registry"):
                raise HTTPException(status_code=400, detail=f"unexpected file {f.filename}")
            p = Path(tmp) / f"{name}.csv"
            p.write_bytes(await f.read())
            loaded[name] = p
        if all(name in loaded for name in ("students", "courses", "attendance", "results")):
            from scripts.validate_students import validate
            errors, _ = validate(Path(tmp))
            if errors:
                raise HTTPException(status_code=400, detail={"validation_errors": errors[:20]})
        try:
            loaded = load_csv_tables(loaded, replace=replace)
        except (ValueError, sqlite3.IntegrityError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "loaded", "rows": loaded, "sqlite": sqlite_health()}
