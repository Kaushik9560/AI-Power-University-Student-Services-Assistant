"""
The single LangGraph workflow (guide §5: "decide what your system actually needs").

    START → classify_query ─┬─ policy ──────────→ retrieve_documents ──────────────┐
                            ├─ personal ───────→ execute_tools ───────────────────┤
                            ├─ eligibility ────→ retrieve_documents → execute_tools┤
                            ├─ multi_step ─────→ retrieve_documents → execute_tools┤
                            └─ clarification / refused ────────────────────────────┤
                                                                                   ↓
                   resolve_sources_and_rules → generate_answer → validate_and_audit → END

One fixed workflow, no loops, no autonomous agents: every question visits at most six nodes.
We deliberately did not add agents — classification, precedence and eligibility are
deterministic steps, so an agent would add latency and remove auditability.
"""
from __future__ import annotations

import time
import uuid
from datetime import date
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (classify_query, execute_tools, generate_answer,
                             resolve_sources_and_rules, retrieve_documents, validate_and_audit)
from app.graph.state import AssistantState


def route_after_classify(state: AssistantState) -> str:
    q = state["query_type"]
    if q == "policy":
        return "retrieve_documents"
    if q == "personal":
        return "execute_tools"
    if q in ("eligibility", "multi_step"):
        return "retrieve_documents"
    return "generate_answer"


def route_after_retrieve(state: AssistantState) -> str:
    return "execute_tools" if state["query_type"] in ("eligibility", "multi_step") else "resolve_sources_and_rules"


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(AssistantState)
    for name, fn in (("classify_query", classify_query), ("retrieve_documents", retrieve_documents),
                     ("execute_tools", execute_tools), ("resolve_sources_and_rules", resolve_sources_and_rules),
                     ("generate_answer", generate_answer), ("validate_and_audit", validate_and_audit)):
        g.add_node(name, fn)
    g.add_edge(START, "classify_query")
    g.add_conditional_edges("classify_query", route_after_classify,
                            ["retrieve_documents", "execute_tools", "generate_answer"])
    g.add_conditional_edges("retrieve_documents", route_after_retrieve,
                            ["execute_tools", "resolve_sources_and_rules"])
    g.add_edge("execute_tools", "resolve_sources_and_rules")
    g.add_edge("resolve_sources_and_rules", "generate_answer")
    g.add_edge("generate_answer", "validate_and_audit")
    g.add_edge("validate_and_audit", END)
    return g.compile()


def initial_state(question: str, student_id: str | None, as_of_date: str | None) -> AssistantState:
    return {"trace_id": uuid.uuid4().hex[:8], "question": question, "student_id": student_id,
            "as_of_date": as_of_date or date.today().isoformat(), "started_at": time.time(), "errors": []}


def run_query(question: str, student_id: str | None, as_of_date: str | None = None) -> AssistantState:
    """Entry point used by the API. `student_id` must come from the X-Student-Id header only."""
    return build_graph().invoke(initial_state(question, student_id, as_of_date))


def run_query_without_langgraph(question: str, student_id: str | None, as_of_date: str | None = None) -> AssistantState:
    """Same routing, plain Python. Used by tests/evaluation in environments without langgraph."""
    s = dict(initial_state(question, student_id, as_of_date))
    s.update(classify_query(s))
    nxt = route_after_classify(s)
    if nxt == "retrieve_documents":
        s.update(retrieve_documents(s))
        nxt = route_after_retrieve(s)
    if nxt == "execute_tools":
        s.update(execute_tools(s))
        nxt = "resolve_sources_and_rules"
    if nxt == "resolve_sources_and_rules":
        s.update(resolve_sources_and_rules(s))
    s.update(generate_answer(s))
    s.update(validate_and_audit(s))
    return s  # type: ignore[return-value]
