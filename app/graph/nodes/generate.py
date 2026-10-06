"""OWNER: llm. TODO steps 1 and 4: generate an answer grounded in state."""

from app.graph.nodes._common import UNKNOWN_ANSWER
from app.graph.state import AssistantState


def generate_node(state: AssistantState) -> AssistantState:
    """Read retrieved context, facts, and rule outcomes, then write ``answer``."""

    return {**state, "answer": UNKNOWN_ANSWER}
