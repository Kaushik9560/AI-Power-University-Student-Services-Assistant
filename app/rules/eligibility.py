"""
Deterministic eligibility (guide R5). Thresholds come from rule_registry, never from code
constants. Each verdict names the rule_id and its source clause so the answer can cite it.

How a rule gets into the registry: data/synthetic/rule_registry.csv is loaded by
scripts/load_students.py; each row points at a doc_id + section in the Source Register.
When a circular changes a threshold, a new row is added with its own effective_from and
the old row gets an effective_to — get_applicable_rule() then picks by date.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any

from app.rag.loader import batch_in_scope, programme_in_scope
from app.tools import student_tools as T


class RuleError(Exception):
    """No applicable rule in the registry for this parameter/date/scope."""


@dataclass
class Verdict:
    eligible: bool
    rule_id: str
    parameter: str
    actual: Any
    operator: str
    threshold: str
    reason: str
    source_doc_id: str
    source_section: str
    extra_rules: list[dict] = field(default_factory=list)   # other rules that were also checked

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# rule lookup + evaluation
# --------------------------------------------------------------------------
def get_applicable_rule(parameter: str, programme: str | None, batch_year: int | None,
                        as_of: date) -> dict[str, Any]:
    candidates = []
    for r in T.list_rules(parameter):
        ef = date.fromisoformat(r["effective_from"]) if r.get("effective_from") else None
        et = date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None
        if ef and ef > as_of:
            continue
        if et and et < as_of:
            continue
        if not programme_in_scope(programme, _scope_list(r.get("scope_programmes"))):
            continue
        if not batch_in_scope(batch_year, r.get("scope_batches")):
            continue
        candidates.append(r)
    if not candidates:
        raise RuleError(f"No rule for {parameter} applicable on {as_of.isoformat()}")
    from app.rag.store import list_register

    sources = {}
    for source in list_register():
        ef, et = source.get("effective_from"), source.get("effective_to")
        if ef and date.fromisoformat(ef) > as_of or et and date.fromisoformat(et) < as_of:
            continue
        if not programme_in_scope(programme, _scope_list(source.get("scope_programmes"))):
            continue
        if not batch_in_scope(batch_year, source.get("scope_batches")):
            continue
        sources[source["doc_id"]] = source
    candidates = [rule for rule in candidates if rule["source_doc_id"] in sources]
    if not candidates:
        raise RuleError(f"No registered source for {parameter}")
    superseding = []
    for source in sources.values():
        if int(source["authority_level"]) <= 2:
            superseding.extend((target.strip(), source["doc_id"])
                               for target in source.get("supersedes", "").split(";") if target.strip())
    def replaced(rule):
        for target, by in superseding:
            doc_id, _, clause = target.partition("#")
            section = rule.get("source_section") or ""
            if by != rule["source_doc_id"] and doc_id == rule["source_doc_id"] and (
                    not clause or section == clause or section.startswith(clause + ".")):
                return True
        return False
    candidates = [rule for rule in candidates if not replaced(rule)]
    if not candidates:
        raise RuleError(f"Unresolved supersession cycle for {parameter}")
    def priority(rule):
        source = sources[rule["source_doc_id"]]
        effective = rule.get("effective_from") or source.get("effective_from") or "0001-01-01"
        return int(source["authority_level"]), -date.fromisoformat(effective).toordinal()
    candidates.sort(key=priority)
    tied = [rule for rule in candidates if priority(rule) == priority(candidates[0])]
    if len({(rule["operator"], rule["value"]) for rule in tied}) > 1:
        raise RuleError(f"Conflicting equally authoritative rules for {parameter}; contact the issuing office")
    return candidates[0]


def _scope_list(v) -> list[str]:
    if not v or str(v).strip().upper() == "ALL":
        return []
    return [s.strip() for s in str(v).replace(",", ";").split(";") if s.strip()]


def evaluate(operator: str, actual: Any, value: str) -> bool:
    """Pure comparison. `value` is the registry text: '75', '65,75' for between, 'FAIL;ABSENT' for in."""
    op = operator.strip().lower()
    if op == "in":
        return str(actual).upper() in {v.strip().upper() for v in value.replace(",", ";").split(";")}
    if op == "not in":
        return str(actual).upper() not in {v.strip().upper() for v in value.replace(",", ";").split(";")}
    if op == "between":
        lo, hi = (float(x) for x in value.replace(";", ",").split(",")[:2])
        return lo <= float(actual) <= hi
    a, v = float(actual), float(value)
    return {">=": a >= v, "<=": a <= v, ">": a > v, "<": a < v, "==": a == v, "!=": a != v}[op]


def _verdict(rule: dict, actual: Any, ok: bool, reason: str, extra: list[dict] | None = None) -> Verdict:
    return Verdict(eligible=ok, rule_id=rule["rule_id"], parameter=rule["parameter"], actual=actual,
                   operator=rule["operator"], threshold=str(rule["value"]), reason=reason,
                   source_doc_id=rule["source_doc_id"], source_section=rule.get("source_section") or "",
                   extra_rules=extra or [])


# --------------------------------------------------------------------------
# the three checks the demos use
# --------------------------------------------------------------------------
def check_exam_eligibility(student: dict, course_code: str, as_of: date) -> Verdict:
    """End-semester exam eligibility: attendance in the course vs min_attendance_pct."""
    rule = get_applicable_rule("min_attendance_pct", student["programme"], student["batch_year"], as_of)
    att = T.get_attendance(student["student_id"], course_code)
    ok = evaluate(rule["operator"], att["attendance_pct"], rule["value"])
    reason = (f"Attendance in {course_code} is {att['attendance_pct']}% "
              f"({att['classes_attended']} of {att['classes_held']} classes); "
              f"the minimum is {rule['value']}% ({rule['rule_id']}, {rule['source_doc_id']} §{rule.get('source_section')}).")
    extra = []
    if not ok:
        try:
            cond = get_applicable_rule("condonation_max_shortage_pct", student["programme"], student["batch_year"], as_of)
            shortage = round(float(rule["value"]) - att["attendance_pct"], 2)
            within = evaluate(cond["operator"], shortage, cond["value"])
            extra.append({"rule_id": cond["rule_id"], "value": f"{cond['operator']} {cond['value']}",
                          "source_doc_id": cond["source_doc_id"], "source_section": cond.get("source_section") or "", "outcome": within,
                          "note": f"shortage of {shortage}% is {'within' if within else 'beyond'} the condonable limit"})
            reason += (f" The shortage of {shortage}% {'may be condoned on medical grounds' if within else 'exceeds the condonable limit'}"
                       f" ({cond['rule_id']}).")
        except RuleError:
            pass
    return _verdict(rule, att["attendance_pct"], ok, reason, extra)


def project_exam_eligibility(student: dict, attendance: dict, future_classes: int, as_of: date) -> Verdict:
    """Attend every one of the next N classes; hypothetical arithmetic never edits records."""
    if not 1 <= future_classes <= 1000:
        raise RuleError("The number of future classes must be between 1 and 1000")
    rule = get_applicable_rule("min_attendance_pct", student["programme"], student["batch_year"], as_of)
    attended = attendance["classes_attended"] + future_classes
    held = attendance["classes_held"] + future_classes
    percentage = T.calculate_attendance_percentage(attended, held)
    eligible = evaluate(rule["operator"], percentage, rule["value"])
    return _verdict(rule, percentage, eligible,
                    f"After attending all {future_classes} next classes, attendance would be {percentage}% "
                    f"({attended} of {held} classes), against the {rule['value']}% minimum "
                    f"({rule['source_doc_id']} §{rule.get('source_section')}).")


def check_supplementary_eligibility(student: dict, course_code: str, as_of: date) -> Verdict:
    """Supplementary: regular result must be FAIL/ABSENT (not DETAINED, not already PASS)."""
    rule = get_applicable_rule("supplementary_regular_result", student["programme"], student["batch_year"], as_of)
    if str(rule["value"]).upper() == "NONE":
        return _verdict(rule, None, False,
                        "The applicable university regulations do not provide supplementary examinations. "
                        "A failed course must be registered again in a subsequent year or summer semester "
                        f"({rule['rule_id']}, {rule['source_doc_id']} §{rule.get('source_section')}).")
    res = T.get_result(student["student_id"], course_code)
    if res["cleared"]:
        return _verdict(rule, res["latest"]["result"], False,
                        f"You have already passed {course_code} ({res['latest']['exam_session']} "
                        f"{res['latest']['exam_type'].lower()}, {res['latest']['total_marks']}/{res['latest']['max_marks']}); "
                        f"a supplementary examination is not applicable.")
    regular = res["regular"]
    if not regular:
        return _verdict(rule, None, False, f"No regular examination result is recorded for {course_code}.")
    ok = evaluate(rule["operator"], regular["result"], rule["value"])
    extra = []
    try:
        attempts_rule = get_applicable_rule("max_supplementary_attempts", student["programme"], student["batch_year"], as_of)
        attempts_ok = evaluate(attempts_rule["operator"], res["supplementary_attempts"], attempts_rule["value"])
        extra.append({"rule_id": attempts_rule["rule_id"], "value": f"{attempts_rule['operator']} {attempts_rule['value']}",
                      "source_doc_id": attempts_rule["source_doc_id"], "source_section": attempts_rule.get("source_section") or "", "outcome": attempts_ok,
                      "note": f"{res['supplementary_attempts']} supplementary attempt(s) used so far"})
        ok = ok and attempts_ok
    except RuleError:
        pass
    if regular["result"].upper() == "DETAINED":
        reason = (f"Your regular result in {course_code} is DETAINED (attendance shortage); detained students must "
                  f"re-register for the course and are not eligible for the supplementary examination "
                  f"({rule['rule_id']}, {rule['source_doc_id']} §{rule.get('source_section')}).")
    else:
        reason = (f"Your regular result in {course_code} ({regular['exam_session']}) is {regular['result']} with "
                  f"{regular['total_marks']}/{regular['max_marks']} marks; students with a {rule['value'].replace(';', ' or ')} "
                  f"result may appear for the supplementary examination ({rule['rule_id']}, "
                  f"{rule['source_doc_id']} §{rule.get('source_section')}).")
    return _verdict(rule, regular["result"], ok, reason, extra)


def check_placement_eligibility(student: dict, as_of: date, assume_cleared: list[str] | None = None) -> Verdict:
    """
    Placement: CGPA rule AND no active backlogs AND aggregate attendance rule.
    `assume_cleared` lets the multi-step path ask "what if these backlogs were cleared".
    """
    sid = student["student_id"]
    assume_cleared = [c.upper() for c in (assume_cleared or [])]
    cgpa_rule = get_applicable_rule("placement_min_cgpa", student["programme"], student["batch_year"], as_of)
    backlog_rule = get_applicable_rule("placement_max_active_backlogs", student["programme"], student["batch_year"], as_of)

    cgpa_ok = evaluate(cgpa_rule["operator"], student["cgpa"], cgpa_rule["value"])
    backlogs = T.get_active_backlogs(sid)
    remaining = [c for c in backlogs["backlog_courses"] if c not in assume_cleared]
    backlog_ok = evaluate(backlog_rule["operator"], len(remaining), backlog_rule["value"])

    extra = [{"rule_id": backlog_rule["rule_id"], "value": f"{backlog_rule['operator']} {backlog_rule['value']}",
              "source_doc_id": backlog_rule["source_doc_id"], "source_section": backlog_rule.get("source_section") or "", "outcome": backlog_ok,
              "note": f"active backlogs: {backlogs['backlog_courses'] or 'none'}"
                      + (f"; assuming {assume_cleared} cleared → {remaining or 'none'}" if assume_cleared else "")}]
    parts = [f"CGPA is {student['cgpa']} (minimum {cgpa_rule['value']}, {cgpa_rule['rule_id']})"
             + (" — satisfied" if cgpa_ok else " — not satisfied"),
             f"active backlogs: {', '.join(backlogs['backlog_courses']) or 'none'}"
             + (f"; if {', '.join(assume_cleared)} is cleared the remaining backlogs are "
                f"{', '.join(remaining) or 'none'}" if assume_cleared else "")
             + f" ({backlog_rule['rule_id']} requires {backlog_rule['operator']} {backlog_rule['value']})"
             + (" — satisfied" if backlog_ok else " — not satisfied")]
    all_ok = cgpa_ok and backlog_ok
    try:
        att_rule = get_applicable_rule("placement_min_aggregate_attendance_pct", student["programme"],
                                       student["batch_year"], as_of)
        agg = T.get_aggregate_attendance(sid, student["current_semester"])
        att_ok = evaluate(att_rule["operator"], agg["attendance_pct"], att_rule["value"])
        extra.append({"rule_id": att_rule["rule_id"], "value": f"{att_rule['operator']} {att_rule['value']}",
                      "source_doc_id": att_rule["source_doc_id"], "source_section": att_rule.get("source_section") or "", "outcome": att_ok,
                      "note": f"aggregate attendance this semester {agg['attendance_pct']}%"})
        parts.append(f"aggregate attendance in semester {student['current_semester']} is {agg['attendance_pct']}% "
                     f"(minimum {att_rule['value']}%, {att_rule['rule_id']})" + (" — satisfied" if att_ok else " — not satisfied"))
        all_ok = all_ok and att_ok
    except (RuleError, T.ToolError):
        pass
    reason = "; ".join(parts) + "."
    return _verdict(cgpa_rule, student["cgpa"], all_ok, reason, extra)
