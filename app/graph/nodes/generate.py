"""
Node 5 — generate_answer. OWNER: llm.

The only node that asks the LLM to write prose. For calculated results the `answer` line was
already written by code (tools.py); the LLM only writes the `explanation`. For retrieved
facts the LLM writes the answer from the evidence and must label every claim [S#].
"""
from __future__ import annotations

import logging

from app.graph.nodes._common import NOT_FOUND_MESSAGE
from app.graph.prompts import SYSTEM_ANSWER, build_answer_prompt
from app.graph.state import AssistantState
from app.services.llm import NOT_FOUND_TOKEN, _terms_covered, get_llm

log = logging.getLogger(__name__)


def generate_answer(state: AssistantState) -> AssistantState:
    qtype = state["query_type"]
    plan = state.get("tool_plan") or {}
    base = {"model_used": plan.get("model", "none"), "llm_calls": plan.get("calls", 0),
            "tokens": plan.get("tokens", 0), "explanation": ""}
    if qtype == "clarification":
        return {**base, "answer_type": "clarification_needed", "answer": state["message"]}
    if qtype == "refused":
        return {**base, "answer_type": "refused", "answer": state["message"]}

    evidence = state.get("evidence") or []
    facts = state.get("facts") or []
    assumptions = state.get("assumptions") or []
    calculated = state.get("calculated_answer") or ""
    unresolved = [c for c in state.get("conflicts") or [] if not c.get("resolved_by")]

    if qtype in ("eligibility", "multi_step") and not calculated and not unresolved:
        missing_rules = [t for t in state.get("tools_invoked", [])
                         if t["tool"] in ("check_exam_eligibility", "check_supplementary_eligibility",
                                          "check_placement_eligibility", "project_exam_eligibility") and t["status"] != "ok"]
        if missing_rules:
            return {**base, "answer_type": "not_found", "answer": NOT_FOUND_MESSAGE,
                    "explanation": _no_record_note(state)}

    if not evidence and not calculated:
        return {**base, "answer_type": "not_found", "answer": NOT_FOUND_MESSAGE,
                "explanation": _no_record_note(state)}

    if not calculated and not facts:
        grounding = "\n".join(f"{ev['title']} {ev['text']}" for ev in evidence)
        if not _terms_covered(state["question"], grounding):
            return {**base, "answer_type": "not_found", "answer": NOT_FOUND_MESSAGE,
                    "explanation": "The retrieved passages do not cover the requested subject."}

    if unresolved and not calculated:
        c = unresolved[0]
        return {**base, "answer_type": "conflict_flagged",
                "answer": ("Conflicting authoritative sources detected. "
                           f"{c['doc_a']} (§{c['section_a']}) states {', '.join(c['values_a'])} while "
                           f"{c['doc_b']} (§{c['section_b']}) states {', '.join(c['values_b'])}; both have the same "
                           "authority level and effective date, so the precedence policy cannot resolve this. "
                           "Please contact the issuing office. Both sources are cited below."),
                "explanation": c["note"]}

    prompt = build_answer_prompt(state["question"], facts, assumptions, evidence)
    try:
        resp = get_llm().complete(SYSTEM_ANSWER, prompt)
        text, model, calls, tokens = (resp.text.strip(), f"{resp.provider}:{resp.model}",
                                    1 + base["llm_calls"], resp.tokens + base["tokens"])
    except Exception as exc:  # noqa: BLE001 — never let an LLM outage break a deterministic answer
        log.exception("LLM failed: %s", exc)
        text, model, calls, tokens = ((NOT_FOUND_TOKEN if not calculated else " ".join(facts)),
                                     "none (llm error)", base["llm_calls"], base["tokens"])

    if calculated:
        explanation = text if NOT_FOUND_TOKEN not in text else " ".join(facts)
        if assumptions:
            explanation += " Assumptions: " + "; ".join(assumptions) + "."
        return {"answer_type": "calculated", "answer": calculated, "explanation": explanation,
                "model_used": model, "llm_calls": calls, "tokens": tokens}

    if NOT_FOUND_TOKEN in text:
        return {"answer_type": "not_found", "answer": NOT_FOUND_MESSAGE, "explanation": "",
                "model_used": model, "llm_calls": calls, "tokens": tokens}
    return {"answer_type": "retrieved_fact", "answer": text, "explanation": state.get("precedence_decision", ""),
            "model_used": model, "llm_calls": calls, "tokens": tokens}


def _no_record_note(state: AssistantState) -> str:
    missing = [t for t in state.get("tools_invoked") or [] if t["status"] != "ok"]
    if missing:
        return "No matching record: " + "; ".join(str(t["output"].get("error")) for t in missing)
    return ""
