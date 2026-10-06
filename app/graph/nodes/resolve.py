"""OWNER: rules. TODO steps 3-5: select rules and derive a verdict."""

from app.graph.state import AssistantState


def resolve_node(state: AssistantState) -> AssistantState:
    """Write applicable rules, outcomes, and a boolean-or-unknown verdict."""

    return {**state, "applicable_rules": [], "rule_outcomes": [], "verdict": None}
