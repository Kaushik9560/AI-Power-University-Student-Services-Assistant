"""Shared workflow assembly; routing edits belong to the rules or rag areas."""

from collections.abc import Callable
from app.graph.state import AssistantState


def build_workflow() -> Callable[[AssistantState], AssistantState]:
    """TODO steps 1-6: compose implemented nodes into the production graph."""

    def placeholder(state: AssistantState) -> AssistantState:
        return state

    return placeholder
