"""
Node 4 — resolve_sources_and_rules. OWNER: rules.
Applies the Annex A precedence policy (app/rules/precedence.py) to the retrieved chunks,
relative to as_of_date and the student's programme/batch. Pure code.
"""
from __future__ import annotations

from datetime import date

from app.graph.nodes._common import question_terms
from app.graph.state import AssistantState
from app.rules.precedence import resolve_sources
from app.graph.nodes.tools import _call
from app.tools import student_tools


def resolve_sources_and_rules(state: AssistantState) -> AssistantState:
    chunks = state.get("retrieved_chunks") or []
    student = state.get("student") or {}
    invoked = list(state.get("tools_invoked") or [])
    if not student and state.get("student_id"):
        student = _call(invoked, "get_student", student_tools.get_student, student_id=state["student_id"]) or {}
    res = resolve_sources(
        chunks,
        programme=student.get("programme"),
        batch_year=student.get("batch_year"),
        as_of=date.fromisoformat(state["as_of_date"]),
        question_terms=question_terms(state["question"]),
    )
    # Keep resolved disagreements in the audit, but give the model only the winning clause.
    overridden = {(c["doc_b"], c["section_b"]) for c in res.conflicts if c.get("resolved_by")}
    evidence = []
    for chunk in res.evidence:
        if (chunk.doc_id, chunk.section) in overridden:
            res.dropped.append({"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id,
                                "reason": "conflicting clause overridden by precedence"})
        else:
            evidence.append(chunk)
    return {
        "evidence": [c.to_dict() for c in evidence],
        "dropped_sources": res.dropped,
        "upcoming_changes": res.upcoming,
        "conflicts": res.conflicts,
        "precedence_decision": res.decision,
        "student": student or None,
        "tools_invoked": invoked,
    }
