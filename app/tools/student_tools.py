"""
Deterministic tools over SQLite (guide R5). Plain functions, plain dicts, no LLM.

Every tool returns a dict that is shown verbatim in the /ask response under tools_invoked
(input + output) and summarised in the audit record. A ToolError means "no record" and is
reported honestly as such rather than guessed around.
"""
from __future__ import annotations

import re
from typing import Any

from app.db.database import get_connection


class ToolError(Exception):
    """Raised when a record needed for an authoritative answer does not exist."""


# --------------------------------------------------------------------------
# students / courses
# --------------------------------------------------------------------------
def get_student(student_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not row:
        raise ToolError(f"No student record for {student_id}")
    return dict(row)


def get_course(course_code: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
    if not row:
        raise ToolError(f"No course {course_code}")
    return dict(row)


def list_courses(programme: str | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if programme:
            rows = conn.execute("SELECT * FROM courses WHERE programme = ? ORDER BY semester, course_code",
                                (programme,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM courses ORDER BY programme, semester, course_code").fetchall()
    return [dict(r) for r in rows]


def student_courses(student_id: str) -> list[dict[str, Any]]:
    """Courses the student has attendance or results for (what 'which course?' can offer)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT c.* FROM courses c
               WHERE c.course_code IN (SELECT course_code FROM attendance WHERE student_id = ?)
                  OR c.course_code IN (SELECT course_code FROM results WHERE student_id = ?)
               ORDER BY c.semester, c.course_code""", (student_id, student_id)).fetchall()
    return [dict(r) for r in rows]


_COMMON_ABBREVIATIONS = {
    "dbms": "database management", "os": "operating system", "ds": "data structure",
    "cn": "computer network", "coa": "computer organi", "daa": "design and analysis",
    "oops": "object oriented", "toc": "theory of computation", "se": "software engineering",
    "ai": "artificial intelligence", "ml": "machine learning", "dld": "digital logic",
}


def find_course_in_text(text: str, student_id: str | None = None) -> dict[str, Any] | None:
    """
    Resolve the course a question refers to, deterministically:
      1. an explicit course code (CS201, JDG101 ...)
      2. the full course name as a substring
      3. the initials of the course name (e.g. "DMS") or a common abbreviation (e.g. "DBMS")
    The student's own courses are preferred when several match.
    """
    tl = " " + text.lower() + " "
    courses = list_courses()
    own = {c["course_code"] for c in student_courses(student_id)} if student_id else set()

    code_hits = [c for c in courses if re.search(rf"\b{re.escape(c['course_code'].lower())}\b", tl)]
    if code_hits:
        return _prefer_own(code_hits, own)

    name_hits = [c for c in courses if c["course_name"].lower() in tl]
    if name_hits:
        return _prefer_own(sorted(name_hits, key=lambda c: -len(c["course_name"])), own)

    for c in courses:
        words = [w for w in re.findall(r"[A-Za-z]+", c["course_name"]) if w.lower() not in ("of", "and", "the", "to", "in")]
        initials = "".join(w[0] for w in words).lower()
        if len(initials) >= 2 and re.search(rf"\b{re.escape(initials)}\b", tl):
            return c
    for abbr, needle in _COMMON_ABBREVIATIONS.items():
        if re.search(rf"\b{abbr}\b", tl):
            hits = [c for c in courses if needle in c["course_name"].lower()]
            if hits:
                return _prefer_own(hits, own)
    # last resort: a distinctive single word of the name (e.g. "Mathematics"), preferring the student's own course
    word_hits = [c for c in courses
                 if any(re.search(rf"\b{w.lower()}", tl) for w in re.findall(r"[A-Za-z]{6,}", c["course_name"]))]
    if word_hits:
        return _prefer_own(sorted(word_hits, key=lambda c: -len(c["course_name"])), own)
    return None


def _prefer_own(hits: list[dict], own: set[str]) -> dict:
    for h in hits:
        if h["course_code"] in own:
            return h
    return hits[0]


# --------------------------------------------------------------------------
# attendance
# --------------------------------------------------------------------------
def calculate_attendance_percentage(classes_attended: int, classes_held: int) -> float:
    """Pure arithmetic, rounded to 2 decimals. The only place attendance % is computed."""
    if classes_held <= 0:
        raise ToolError("classes_held must be > 0")
    return round(100.0 * classes_attended / classes_held, 2)


def get_attendance(student_id: str, course_code: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND course_code = ?",
                           (student_id, course_code)).fetchone()
    if not row:
        raise ToolError(f"No attendance record for {student_id} in {course_code}")
    pct = calculate_attendance_percentage(row["classes_attended"], row["classes_held"])
    return {"course_code": course_code, "classes_held": row["classes_held"],
            "classes_attended": row["classes_attended"], "attendance_pct": pct}


def get_aggregate_attendance(student_id: str, semester: int | None = None) -> dict[str, Any]:
    """Aggregate across courses (optionally one semester): total attended / total held."""
    with get_connection() as conn:
        if semester:
            rows = conn.execute(
                """SELECT a.* FROM attendance a JOIN courses c ON c.course_code = a.course_code
                   WHERE a.student_id = ? AND c.semester = ?""", (student_id, semester)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
    if not rows:
        raise ToolError(f"No attendance records for {student_id}")
    held = sum(r["classes_held"] for r in rows)
    att = sum(r["classes_attended"] for r in rows)
    return {"courses": len(rows), "semester": semester, "classes_held": held, "classes_attended": att,
            "attendance_pct": calculate_attendance_percentage(att, held)}


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------
def get_results(student_id: str, course_code: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE student_id = ? AND course_code = ? ORDER BY exam_session, exam_type",
            (student_id, course_code)).fetchall()
    return [dict(r) for r in rows]


def get_result(student_id: str, course_code: str) -> dict[str, Any]:
    """Latest result for the course plus the regular-exam result (needed for supplementary rules)."""
    rows = get_results(student_id, course_code)
    if not rows:
        raise ToolError(f"No result record for {student_id} in {course_code}")
    regular = [r for r in rows if r["exam_type"].upper() == "REGULAR"]
    latest = rows[-1]
    return {
        "course_code": course_code,
        "latest": _slim(latest),
        "regular": _slim(regular[-1]) if regular else None,
        "attempts": len(rows),
        "supplementary_attempts": sum(1 for r in rows if r["exam_type"].upper() == "SUPPLEMENTARY"),
        "cleared": latest["result"].upper() == "PASS",
    }


def _slim(r: dict) -> dict:
    return {k: r[k] for k in ("exam_session", "exam_type", "internal_marks", "external_marks",
                              "total_marks", "max_marks", "result")}


def get_active_backlogs(student_id: str) -> dict[str, Any]:
    """
    Backlogs computed from results: a course whose latest result is FAIL/ABSENT/DETAINED.
    Also returns the students.active_backlogs column so inconsistencies are visible.
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM results WHERE student_id = ? ORDER BY course_code, exam_session, exam_type",
                            (student_id,)).fetchall()
        stored = conn.execute("SELECT active_backlogs FROM students WHERE student_id = ?", (student_id,)).fetchone()
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r["course_code"]] = dict(r)
    backlog_courses = sorted(code for code, r in latest.items() if r["result"].upper() != "PASS")
    return {"backlog_courses": backlog_courses, "count": len(backlog_courses),
            "stored_active_backlogs": stored["active_backlogs"] if stored else None}


# --------------------------------------------------------------------------
# rule registry
# --------------------------------------------------------------------------
def list_rules(parameter: str | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if parameter:
            rows = conn.execute("SELECT * FROM rule_registry WHERE parameter = ? ORDER BY effective_from",
                                (parameter,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM rule_registry ORDER BY rule_id").fetchall()
    return [dict(r) for r in rows]
