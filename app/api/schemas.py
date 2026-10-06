"""API contract from the hackathon guide §6 (Pydantic v2)."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

AnswerType = Literal["retrieved_fact", "calculated", "not_found", "clarification_needed", "refused", "conflict_flagged"]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    as_of_date: Optional[str] = Field(None, description="YYYY-MM-DD; defaults to today")
    previous_trace_id: Optional[str] = Field(None, pattern=r"^[0-9a-f]{8}$",
                                            description="Previous response trace for a clarification follow-up")

    @field_validator("as_of_date")
    @classmethod
    def _valid_date(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        return date.fromisoformat(v).isoformat()


class Citation(BaseModel):
    label: Optional[str] = None
    doc_id: str
    title: str
    section: Optional[str] = None
    page: Optional[int] = None
    version: Optional[str] = None
    effective_from: Optional[str] = None
    authority_level: Optional[int] = None
    issuer: Optional[str] = None
    excerpt: Optional[str] = None


class ToolInvocation(BaseModel):
    tool: str
    input: dict[str, Any] = {}
    output: Any = None
    status: str = "ok"
    ms: int = 0


class AppliedRule(BaseModel):
    rule_id: str
    value: str
    source_doc_id: str
    source_section: Optional[str] = None
    outcome: Optional[bool] = None


class AskResponse(BaseModel):
    trace_id: str
    answer: str
    answer_type: AnswerType
    citations: list[Citation] = []
    tools_invoked: list[ToolInvocation] = []
    applied_rules: list[AppliedRule] = []
    conflicts_detected: list[dict[str, Any]] = []
    explanation: str = ""
    as_of_date: str
    # extras (not in the mandatory contract, useful for the UI and judges)
    verdict: Optional[bool] = None
    assumptions: list[str] = []
    upcoming_changes: list[dict[str, Any]] = []
    query_type: Optional[str] = None
    latency_ms: Optional[int] = None
    clarification_options: list[str] = []


class IngestResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    status: str
    title: Optional[str] = None
    total_documents: int = 0
    rules_registered: list[str] = []


class HealthResponse(BaseModel):
    status: str
    api: str
    vector_store: dict[str, Any]
    sqlite: dict[str, Any]
    llm: dict[str, Any]
    embeddings: dict[str, Any]
    audit: dict[str, Any]
