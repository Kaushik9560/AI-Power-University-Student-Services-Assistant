"""OWNER: audit-eval. TODO step 6: validate grounding and create an audit event."""

from app.graph.state import AssistantState


def validate_node(state: AssistantState) -> AssistantState:
    """Write validation errors and an audit identifier."""

    return {**state, "validation_errors": []}
