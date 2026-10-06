"""
Node 1 — classify_query. OWNER: routing / security.

Deterministic keyword routing (no LLM): the routing decides which tools run and whether
personal data is touched, so it must be predictable and testable. Also enforces R7:
identity comes only from the header; any other student id in the text is refused.

query_type → route
  policy        retrieve → resolve → generate            (policy fact, procedure)
  personal      tools → generate                         (attendance, marks, CGPA, backlogs)
  eligibility   retrieve → tools → resolve → generate    (exam / supplementary / placement)
  multi_step    retrieve → tools → resolve → generate    (what-if chains)
  clarification / refused → generate (no retrieval, no tools)
"""
from __future__ import annotations

import re

from app.graph.nodes._common import LOGIN_REQUIRED_MESSAGE, OTHER_STUDENT_MESSAGE, STUDENT_ID_PATTERN
from app.graph.state import AssistantState
from app.tools import student_tools as T

_PERSONAL = ("my ", "am i", "do i", "can i", "will i", "i failed", "i have", "i got", "i scored",
             "i missed", "i was", "i am", "mine", "myself", "me ")
_DATA_WORDS = ("attendance", "marks", "result", "cgpa", "backlog", "grade", "score", "percentage", "sgpa",
               "credits", "absent", "detained", "passed", "failed", "fail")
_ELIGIBILITY = ("eligib", "qualify", "allowed to", "permitted to", "can i sit", "can i appear", "can i write",
                "can i register", "will i be able")
_HYPOTHETICAL = ("if i", "suppose", "assuming", "once i", "after i clear", "after i pass", "what if", "if my")
_PROCEDURE = ("how do i", "how to", "how can i", "procedure", "process", "steps", "apply", "where do i")
_TOPICS = {
    "exam": ("end-semester", "end semester", "semester exam", "end sem", "final exam", "appear for the exam", "sit the exam",
             "write the exam", "examination"),
    "supplementary": ("supplementary", "supply exam", "re-exam", "reappear", "backlog exam"),
    "placement": ("placement", "campus drive", "recruit", "placed"),
    "scholarship": ("scholarship", "fee waiver", "merit-cum-means"),
    "hostel": ("hostel", "curfew", "warden"),
    "attendance": ("attendance", "condon"),
    "promotion": ("promot", "next year", "detain"),
    "backlogs": ("backlog",),
    "cgpa": ("cgpa", "gpa"),
}


def classify_query(state: AssistantState) -> AssistantState:
    q = state["question"].strip()
    ql = " " + q.lower() + " "
    student_id = state.get("student_id")

    # ---- R7: identity only from the header; refuse other ids in the text ----
    mentioned = {m.upper() for m in STUDENT_ID_PATTERN.findall(q)}
    foreign = mentioned - ({student_id.upper()} if student_id else set())
    if foreign:
        return {"query_type": "refused", "question_category": "unauthorised_access", "entities": {},
                "message": OTHER_STUDENT_MESSAGE}

    topics = [name for name, words in _TOPICS.items() if any(w in ql for w in words)]
    if re.search(r"\b(?:exam|exams|ese|mse)\b", ql) and "exam" not in topics:
        topics.append("exam")
    is_personal = any(m in ql for m in _PERSONAL)
    is_elig = any(w in ql for w in _ELIGIBILITY)
    is_hyp = any(w in ql for w in _HYPOTHETICAL)
    is_proc = any(w in ql for w in _PROCEDURE)
    has_data = any(w in ql for w in _DATA_WORDS)
    # Short topic replies are common in chat. Ask for the course rather than running
    # a document search for an incomplete phrase such as "end-semester".
    if re.fullmatch(r"(?:end[ -]?(?:semester|sem)(?:\s+exams?)?|exams?|ese|mse)", q.lower().strip(" .?!")):
        is_elig = True
        is_personal = True
        if "exam" not in topics:
            topics.append("exam")

    # ---- eligibility with no subject → ask back ----
    if is_elig and not topics:
        return {"query_type": "clarification", "question_category": "clarification", "entities": {},
                "message": "Are you asking about end-semester exam eligibility, supplementary examination "
                           "eligibility, or placement eligibility?",
                "clarification_options": ["End-semester exam", "Supplementary exam", "Placement"]}

    if is_elig and is_hyp:
        qtype, category = "multi_step", "multi_step_what_if"
    elif is_elig and (is_personal or student_id and "eligib" in ql):
        qtype, category = "eligibility", "personal_eligibility"
    elif is_personal and has_data and not is_proc:
        qtype, category = "personal", "personal_data"
    elif is_proc:
        qtype, category = "policy", "procedure"
    else:
        qtype, category = "policy", "policy_fact"

    # ---- personal paths need an identity ----
    if qtype in ("personal", "eligibility", "multi_step") and not student_id:
        if qtype == "personal":
            return {"query_type": "refused", "question_category": "no_identity", "entities": {},
                    "message": LOGIN_REQUIRED_MESSAGE}
        return {"query_type": "refused", "question_category": "no_identity", "entities": {},
                "message": LOGIN_REQUIRED_MESSAGE}

    course = T.find_course_in_text(q, student_id) if qtype != "policy" else None
    needs_course = qtype == "personal" and any(w in ql for w in ("attendance", "marks", "result", "grade", "score", "passed", "failed", "fail"))
    needs_course = needs_course or (qtype in ("eligibility", "multi_step") and
                                    ("supplementary" in topics or ("exam" in topics and "placement" not in topics)))
    if needs_course and course is None:
        choices = [f"{c['course_code']} {c['course_name']}" for c in T.student_courses(student_id)[:8]]
        options = ", ".join(choices)
        return {"query_type": "clarification", "question_category": "clarification", "entities": {"topics": topics},
                "message": "Which course are you asking about?" + (f" Your courses: {options}." if options else ""),
                "clarification_options": choices}

    return {"query_type": qtype, "question_category": category,
            "entities": {"course": course, "topics": topics, "hypothetical": is_hyp}}
