"""Node 2 — retrieve_documents. OWNER: rag. Top-k chunks from ChromaDB; precedence is applied later."""
from __future__ import annotations

from app.config import settings
from app.graph.state import AssistantState
from app.rag.store import get_store


def retrieve_documents(state: AssistantState) -> AssistantState:
    query = state["question"]
    topics = state.get("entities", {}).get("topics") or []
    if state["query_type"] in ("eligibility", "multi_step"):
        # Pull the rule text for every topic the question touches (e.g. supplementary + placement).
        query = query + " " + " ".join(f"{t} eligibility rule" for t in topics)
    chunks = get_store().query(query, top_k=settings.RETRIEVAL_TOP_K)
    return {"retrieved_chunks": chunks,
            "sources_retrieved": [{"doc_id": c.doc_id, "section": c.section, "page": c.page, "score": c.score}
                                  for c in chunks]}
