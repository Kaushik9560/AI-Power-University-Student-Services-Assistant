"""Shared API contract. Announce changes because the UI and evaluation depend on it."""

from typing import Any
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """A student question submitted to the assistant."""

    question: str = Field(min_length=1)
    student_id: str | None = None


class AskResponse(BaseModel):
    """Stable response shape consumed by the UI and evaluator."""

    answer: str
    verdict: bool | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    applicable_rules: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    audit_id: str | None = None
