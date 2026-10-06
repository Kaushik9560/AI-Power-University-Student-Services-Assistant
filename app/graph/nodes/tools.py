"""OWNER: student-data. TODO step 2: collect student facts through plain tools."""

from app.graph.state import AssistantState


def tools_node(state: AssistantState) -> AssistantState:
    """Write facts, tool names, and the normalized student record."""

    return {
        **state,
        "tool_results": {"facts": []},
        "tools_used": [],
        "student": {},
    }
