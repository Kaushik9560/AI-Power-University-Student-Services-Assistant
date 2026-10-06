"""
Node 6 — validate_and_audit. OWNER: audit-eval.
Citation integrity, identity-leak scrubbing, upcoming-change notes, latency, audit record.
"""
from __future__ import annotations

import logging
import re
import time

from app.audit.store import write_audit
from app.graph.nodes._common import STUDENT_ID_PATTERN
from app.graph.state import AssistantState
from app.graph.nodes._common import NOT_FOUND_MESSAGE
from app.rag.attribution import attribute_unlabelled_answer, normalise_labels
from app.services.llm import _terms_covered

log = logging.getLogger(__name__)
_LABEL = re.compile(r"\[S(\d+)\]")


def validate_and_audit(state: AssistantState) -> AssistantState:
    evidence = state.get("evidence") or []
    answer = normalise_labels(state.get("answer", ""))
    explanation = normalise_labels(state.get("explanation", ""))
    errors = list(state.get("errors", []))
    atype = state.get("answer_type")
    citations: list[dict] = []

    if atype == "retrieved_fact":
        referenced = {int(n) for n in _LABEL.findall(answer) if 1 <= int(n) <= len(evidence)}
        if evidence and not referenced:
            referenced = attribute_unlabelled_answer(answer, evidence)
            errors.append("answer had no [S#] labels; matched supported figures and terms to evidence")
            if referenced:
                answer += " " + " ".join(f"[S{index}]" for index in sorted(referenced))
            else:
                atype = "not_found"
                answer, explanation = NOT_FOUND_MESSAGE, "The model's unlabelled claims could not be attributed to supporting evidence."
        citations = _citations(evidence, referenced)
        answer = _strip_bad_labels(answer, len(evidence))
        if atype == "retrieved_fact" and state.get("upcoming_changes"):
            relevant = [u for u in state["upcoming_changes"] if _terms_covered(
                state["question"], f"{u['title']} {u.get('excerpt', '')}")]
            if relevant:
                u = relevant[0]
                answer += (f" Future notice: {u['title']} takes effect on {u['effective_from']}; "
                           "it is not applied to this answer.")
    elif atype == "calculated":
        # Cite the clauses the applied rules point at, plus any evidence the explanation labelled.
        rule_docs = [(r["source_doc_id"], r.get("source_section") or "") for r in state.get("applied_rules") or []]
        referenced = {int(n) for n in _LABEL.findall(explanation) if 1 <= int(n) <= len(evidence)}
        citations = _citations(evidence, referenced)
        citations += _rule_citations(rule_docs, evidence, citations)
        explanation = _strip_bad_labels(explanation, len(evidence))
    elif atype == "conflict_flagged":
        docs = {d for c in state.get("conflicts") or [] if not c.get("resolved_by") for d in (c["doc_a"], c["doc_b"])}
        citations = _citations(evidence, {i for i, ev in enumerate(evidence, start=1) if ev["doc_id"] in docs})

    # R7: never leak another student's id in prose.
    own = (state.get("student_id") or "").upper()
    for field_name, text in (("answer", answer), ("explanation", explanation)):
        leaked = {m.upper() for m in STUDENT_ID_PATTERN.findall(text)} - {own}
        if leaked:
            errors.append(f"scrubbed foreign student id(s) from {field_name}")
            text = STUDENT_ID_PATTERN.sub(lambda m: m.group(0) if m.group(0).upper() == own else "[redacted]", text)
            if field_name == "answer":
                answer = text
            else:
                explanation = text

    latency_ms = int((time.time() - state["started_at"]) * 1000)
    final = {**state, "answer_type": atype, "answer": answer, "explanation": explanation, "citations": citations,
             "errors": errors, "latency_ms": latency_ms}
    final.pop("retrieved_chunks", None)
    try:
        write_audit(final)
    except Exception as exc:  # noqa: BLE001 — auditing must never break the answer
        log.exception("audit write failed: %s", exc)
    return {"answer_type": atype, "answer": answer, "explanation": explanation, "citations": citations, "errors": errors,
            "latency_ms": latency_ms}


def _cite(ev: dict, label: str) -> dict:
    return {"label": label, "doc_id": ev["doc_id"], "title": ev["title"], "section": ev.get("section") or None,
            "page": ev.get("page"), "version": ev.get("version"), "effective_from": ev.get("effective_from"),
            "authority_level": ev.get("authority_level"), "issuer": ev.get("issuer"), "excerpt": ev["text"][:300]}


def _citations(evidence: list[dict], indexes: set[int]) -> list[dict]:
    seen, out = set(), []
    for i in sorted(indexes):
        ev = evidence[i - 1]
        key = (ev["doc_id"], ev.get("section"))
        if key not in seen:
            seen.add(key)
            out.append(_cite(ev, f"S{i}"))
    return out


def _rule_citations(rule_docs: list[tuple[str, str]], evidence: list[dict], existing: list[dict]) -> list[dict]:
    """Cite the clause each applied rule points at: use the retrieved chunk if we have it, else the register."""
    from app.rag.store import get_store, list_register

    out: list[dict] = []
    register = {r["doc_id"]: r for r in list_register()}

    def covered(doc_id: str, section: str) -> bool:
        return any(c["doc_id"] == doc_id and (not section or (c.get("section") or "").startswith(section))
                   for c in existing + out)

    for doc_id, section in rule_docs:
        if covered(doc_id, section):
            continue
        match = next((ev for ev in evidence if ev["doc_id"] == doc_id and (not section or (ev.get("clause") or "").startswith(section))), None)
        if match is None and section and hasattr(get_store(), "lookup_clause"):
            match = get_store().lookup_clause(doc_id, section)
        if match:
            out.append(_cite(match, "rule"))
        elif doc_id in register:
            r = register[doc_id]
            out.append({"label": "rule", "doc_id": doc_id, "title": r["title"], "section": section or None, "page": None,
                        "version": r["version"], "effective_from": r["effective_from"], "authority_level": r["authority_level"],
                        "issuer": r["issuer"], "excerpt": None})
    return out


def _strip_bad_labels(text: str, n: int) -> str:
    return _LABEL.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= n else "", text)
