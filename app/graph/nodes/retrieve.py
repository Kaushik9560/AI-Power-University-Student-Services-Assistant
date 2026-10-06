"""OWNER: rag. TODO steps 1 and 5: retrieve relevant cited documents."""

from app.graph.state import AssistantState
from app.rag.store import search


def retrieve_node(state: AssistantState) -> AssistantState:
    """Write ranked documents to ``retrieved_documents``."""

    return {**state, "retrieved_documents": search(state.get("question", ""))}
