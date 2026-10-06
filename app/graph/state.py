"""Shared LangGraph state. A plain TypedDict so every node's output is inspectable and auditable."""
from __future__ import annotations

from typing import Any, Literal, TypedDict

QueryType = Literal["policy", "personal", "eligibility", "multi_step", "clarification", "refused"]
AnswerType = Literal["retrieved_fact", "calculated", "not_found", "clarification_needed", "refused", "conflict_flagged"]


class AssistantState(TypedDict, total=False):
    # ---- input ----------------------------------------------------------
    trace_id: str
    question: str
    student_id: str | None          # ONLY from the X-Student-Id header
    as_of_date: str                 # YYYY-MM-DD, defaults to today
    started_at: float

    # ---- classify -------------------------------------------------------
    query_type: QueryType
    question_category: str          # finer label for the audit (policy_fact, procedure, personal_data, ...)
    entities: dict[str, Any]        # {"course": {...} | None, "topics": [...], "needs_course": bool}
    message: str                    # text for clarification / refused answers

    # ---- retrieve + resolve ---------------------------------------------
    retrieved_chunks: list[Any]     # RetrievedChunk objects (internal)
    sources_retrieved: list[dict]   # audit view: {doc_id, section, score}
    evidence: list[dict]            # chunks that survived precedence
    dropped_sources: list[dict]
    upcoming_changes: list[dict]
    conflicts: list[dict]
    precedence_decision: str

    # ---- tools + rules --------------------------------------------------
    student: dict | None
    tools_invoked: list[dict]       # {tool, input, output, status, ms}
    facts: list[str]                # deterministic sentences the LLM may repeat but not alter
    assumptions: list[str]          # stated assumptions for what-if questions
    applied_rules: list[dict]       # {rule_id, value, source_doc_id, source_section}
    verdict: bool | None
    calculated_answer: str          # the one-line answer written by code for calculated results
    tool_plan: dict                  # bounded model proposal, validation/fallback and token usage

    # ---- output ----------------------------------------------------------
    answer_type: AnswerType
    answer: str
    explanation: str
    citations: list[dict]
    errors: list[str]
    model_used: str
    llm_calls: int
    tokens: int
    latency_ms: int
