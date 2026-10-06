"""
Node 3 — execute_tools. OWNER: student-data / rules.

Runs deterministic tools and eligibility checks, records each call with input/output/status/ms,
and writes plain-language `facts` (and `assumptions` for what-if questions) that the LLM may
repeat but never alter. The one-line `calculated_answer` is also written here, by code.
"""
from __future__ import annotations

import time
import re
from datetime import date

from app.graph.state import AssistantState
from app.rules import eligibility as E
from app.tools import student_tools as T
from app.services.tool_planner import propose_tools


def _call(record: list, name: str, fn, **kwargs):
    """Run a tool, time it, append an audit-friendly record. Returns the output or None."""
    t0 = time.perf_counter()
    try:
        out = fn(**kwargs)
        if name == "get_student":
            out = {key: value for key, value in out.items() if key != "full_name"}
        record.append({"tool": name, "input": kwargs, "output": out, "status": "ok",
                       "ms": int((time.perf_counter() - t0) * 1000)})
        return out
    except (T.ToolError, E.RuleError) as exc:
        record.append({"tool": name, "input": kwargs, "output": {"error": str(exc)}, "status": "no_record",
                       "ms": int((time.perf_counter() - t0) * 1000)})
        return None


def execute_tools(state: AssistantState) -> AssistantState:
    sid = state["student_id"]
    as_of = date.fromisoformat(state["as_of_date"])
    qtype = state["query_type"]
    topics = state.get("entities", {}).get("topics") or []
    course = state.get("entities", {}).get("course")
    code = course["course_code"] if course else None
    ql = state["question"].lower()
    future = re.search(r"(?:next\s+(\d+)\s+classes|attend\s+(?:all\s+)?(\d+)\s+(?:more|next|additional)\s+classes)", ql)
    future_classes = int(next(value for value in future.groups() if value)) if future else None
    if qtype == "personal":
        allowed = ["get_student", "get_attendance" if code and "attendance" in ql else
                   "get_result" if code else "get_active_backlogs" if "backlog" in ql else "get_student"]
    elif qtype == "eligibility":
        allowed = ["get_student", "check_placement_eligibility" if "placement" in topics else
                   "check_supplementary_eligibility" if "supplementary" in topics else "check_exam_eligibility"]
    elif future_classes is not None and code:
        allowed = ["get_student", "get_attendance", "project_exam_eligibility"]
    else:
        allowed = ["get_student", "get_result", "check_supplementary_eligibility", "check_placement_eligibility"]
    plan = propose_tools(state["question"], list(dict.fromkeys(allowed)))

    invoked: list[dict] = []
    facts: list[str] = []
    assumptions: list[str] = []
    rules: list[dict] = []
    verdict: bool | None = None
    calculated = ""

    student = _call(invoked, "get_student", T.get_student, student_id=sid)
    if not student:
        return {"student": None, "tools_invoked": invoked, "facts": [], "assumptions": [], "applied_rules": [],
                "verdict": None, "calculated_answer": "",
                "tool_plan": plan,
                "errors": state.get("errors", []) + [f"no student record for {sid}"]}
    facts.append(f"Student {sid} is in {student['programme']} (batch {student['batch_year']}, "
                 f"semester {student['current_semester']}).")

    # ---------------- personal data ----------------
    if qtype == "personal":
        ql = state["question"].lower()
        if code and "attendance" in ql:
            att = _call(invoked, "get_attendance", T.get_attendance, student_id=sid, course_code=code)
            if att:
                calculated = (f"Your attendance in {code} ({course['course_name']}) is {att['attendance_pct']}% "
                              f"({att['classes_attended']} of {att['classes_held']} classes).")
                facts.append(calculated)
                _attendance_context(rules, facts, student, att, as_of)
        elif code:
            res = _call(invoked, "get_result", T.get_result, student_id=sid, course_code=code)
            if res:
                r = res["latest"]
                calculated = (f"Your latest result in {code} ({course['course_name']}) is {r['result']}: "
                              f"{r['total_marks']}/{r['max_marks']} (internal {r['internal_marks']}, "
                              f"external {r['external_marks']}) in the {r['exam_session']} {r['exam_type'].lower()} examination.")
                facts.append(calculated)
        elif "attendance" in ql:
            agg = _call(invoked, "get_aggregate_attendance", T.get_aggregate_attendance, student_id=sid, semester=None)
            if agg:
                calculated = (f"Your aggregate attendance across {agg['courses']} courses is {agg['attendance_pct']}% "
                              f"({agg['classes_attended']} of {agg['classes_held']} classes).")
                facts.append(calculated)
        elif "backlog" in ql:
            b = _call(invoked, "get_active_backlogs", T.get_active_backlogs, student_id=sid)
            if b:
                calculated = (f"You have {b['count']} active backlog(s)"
                              + (f": {', '.join(b['backlog_courses'])}." if b["backlog_courses"] else "."))
                facts.append(calculated)
        else:  # cgpa / general profile
            calculated = f"Your CGPA is {student['cgpa']} and you have {student['active_backlogs']} active backlog(s)."
            facts.append(calculated)

    # ---------------- eligibility ----------------
    elif qtype == "eligibility":
        v = None
        if "placement" in topics:
            v = _call(invoked, "check_placement_eligibility", E.check_placement_eligibility, student=student, as_of=as_of)
            label = "campus placement registration"
        elif "supplementary" in topics and code:
            v = _call(invoked, "check_supplementary_eligibility", E.check_supplementary_eligibility,
                      student=student, course_code=code, as_of=as_of)
            label = f"the supplementary examination in {code}"
        elif code:
            v = _call(invoked, "check_exam_eligibility", E.check_exam_eligibility, student=student, course_code=code, as_of=as_of)
            label = f"the end-semester examination in {code}"
        else:
            label = ""
        if v:
            verdict = v.eligible
            calculated = f"{'Yes — you are' if verdict else 'No — you are not'} eligible for {label}."
            facts.append(calculated)
            facts.append(v.reason)
            _collect_rules(rules, v)

    # ---------------- multi-step / what-if ----------------
    elif qtype == "multi_step" and future_classes is not None and code:
        attendance = _call(invoked, "get_attendance", T.get_attendance, student_id=sid, course_code=code)
        if attendance:
            projection = _call(invoked, "project_exam_eligibility", E.project_exam_eligibility,
                               student=student, attendance=attendance, future_classes=future_classes, as_of=as_of)
            if projection:
                verdict = projection.eligible
                calculated = (f"{'Yes' if verdict else 'No'} — after attending the next {future_classes} classes, "
                              f"you {'would meet' if verdict else 'would not meet'} the attendance requirement for {code}.")
                facts.extend([calculated, projection.reason])
                assumptions.extend([f"you attend every one of the next {future_classes} scheduled classes",
                                    "no other classes are held, and the cited attendance rule remains applicable"])
                _collect_rules(rules, projection)
    elif qtype == "multi_step":
        sv = None
        if code:
            res = _call(invoked, "get_result", T.get_result, student_id=sid, course_code=code)
            if res:
                r = res["regular"] or res["latest"]
                facts.append(f"Your recorded regular result in {code} is {r['result']} ({r['total_marks']}/{r['max_marks']}, {r['exam_session']}).")
                if res["cleared"]:
                    facts.append(f"Note: your latest result in {code} is already PASS, so no supplementary is pending.")
            sv = _call(invoked, "check_supplementary_eligibility", E.check_supplementary_eligibility,
                       student=student, course_code=code, as_of=as_of)
            if sv:
                facts.append(f"Supplementary eligibility in {code}: {'eligible' if sv.eligible else 'not eligible'}. {sv.reason}")
                _collect_rules(rules, sv)
        if "placement" in topics:
            now = _call(invoked, "check_placement_eligibility", E.check_placement_eligibility, student=student, as_of=as_of)
            if now:
                facts.append(f"Placement eligibility today: {'eligible' if now.eligible else 'not eligible'}. {now.reason}")
                _collect_rules(rules, now)
            if code:
                assumptions.append(f"you pass the supplementary examination in {code} and the Controller of Examinations declares the result")
                assumptions.append(f"your CGPA stays at {student['cgpa']} and no new backlogs arise")
                after = _call(invoked, "check_placement_eligibility", E.check_placement_eligibility,
                              student=student, as_of=as_of, assume_cleared=[code])
                if after:
                    verdict = after.eligible
                    calculated = (f"{'Yes' if verdict else 'No'} — if you clear {code} in the supplementary examination you "
                                  f"{'would become' if verdict else 'would still not be'} eligible for campus placements.")
                    facts.append(calculated)
                    facts.append(f"After clearing {code}: {after.reason}")
                    _collect_rules(rules, after)
        elif sv is not None:
            verdict = sv.eligible
            calculated = f"{'Yes' if verdict else 'No'} — you {'are' if verdict else 'are not'} eligible for the supplementary examination in {code}."

    return {"student": student, "tools_invoked": invoked, "facts": facts, "assumptions": assumptions,
            "applied_rules": _dedupe(rules), "verdict": verdict, "calculated_answer": calculated,
            "tool_plan": plan}


def _attendance_context(rules: list, facts: list, student: dict, att: dict, as_of: date) -> None:
    """For 'what is my attendance' also tell the student where they stand against the threshold."""
    try:
        rule = E.get_applicable_rule("min_attendance_pct", student["programme"], student["batch_year"], as_of)
    except E.RuleError:
        return
    ok = E.evaluate(rule["operator"], att["attendance_pct"], rule["value"])
    rules.append({"rule_id": rule["rule_id"], "value": f"{rule['operator']}{rule['value']}%",
                  "source_doc_id": rule["source_doc_id"], "source_section": rule.get("source_section") or ""})
    facts.append(f"This is {'at or above' if ok else 'below'} the {rule['value']}% minimum required for the "
                 f"end-semester examination ({rule['rule_id']}, {rule['source_doc_id']} §{rule.get('source_section')}).")


def _collect_rules(rules: list, v: E.Verdict) -> None:
    rules.append({"rule_id": v.rule_id, "value": f"{v.operator}{v.threshold}", "source_doc_id": v.source_doc_id,
                  "source_section": v.source_section, "outcome": v.eligible})
    for extra in v.extra_rules:
        rules.append({"rule_id": extra["rule_id"], "value": extra["value"], "source_doc_id": extra["source_doc_id"],
                      "source_section": extra.get("source_section") or "", "outcome": extra.get("outcome")})


def _dedupe(rules: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rules:
        if r["rule_id"] not in seen:
            seen.add(r["rule_id"])
            out.append(r)
    return out
