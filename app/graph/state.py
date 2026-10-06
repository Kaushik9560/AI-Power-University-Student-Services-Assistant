"""Shared append-only workflow state contract."""

from typing import Any, TypedDict


class AssistantState(TypedDict, total=False):
    """Keys written by graph nodes; add new keys without renaming existing ones."""

    question: str
    student_id: str | None
    retrieved_documents: list[dict[str, Any]]
    sources_retrieved: list[dict[str, Any]]
    tool_results: dict[str, Any]
    tools_used: list[str]
    student: dict[str, Any]
    applicable_rules: list[dict[str, Any]]
    rule_outcomes: list[dict[str, Any]]
    verdict: bool | None
    answer: str
    citations: list[dict[str, Any]]
    validation_errors: list[str]
    audit_id: str
