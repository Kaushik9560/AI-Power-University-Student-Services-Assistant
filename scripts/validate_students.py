"""
Validate a set of Annex C CSVs (schema + logical constraints) and report violations.

    python scripts/validate_students.py                      # data/synthetic
    python scripts/validate_students.py --dir test_students/ # judges' data before loading

Checks: id formats, reserved ranges, referential integrity, 0 <= attended <= held, marks in range,
total = internal + external, result consistent with marks (PASS: total>=40 and external>=21),
ABSENT/DETAINED have external 0, students.active_backlogs == backlogs derived from results,
programme of each course matches the student's programme, edge-case coverage (informational).
Exit code 1 if any violation.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PASS_TOTAL, PASS_EXT = 40, 21


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate(d: Path) -> tuple[list[str], list[str]]:
    errors, info = [], []
    students, courses = read(d / "students.csv"), read(d / "courses.csv")
    attendance, results = read(d / "attendance.csv"), read(d / "results.csv")
    sids = {s["student_id"] for s in students}
    codes = {c["course_code"]: c for c in courses}
    prog = {s["student_id"]: s["programme"] for s in students}

    for s in students:
        sid = s["student_id"]
        if not re.fullmatch(r"S\d{4}", sid):
            errors.append(f"students: bad id {sid}")
        if not (1 <= int(s["current_semester"]) <= 10):
            errors.append(f"students {sid}: semester out of range")
        if not (0 <= float(s["cgpa"]) <= 10):
            errors.append(f"students {sid}: cgpa out of range")
        if int(s["active_backlogs"]) < 0:
            errors.append(f"students {sid}: negative backlogs")
    if len(sids) != len(students):
        errors.append("students: duplicate ids")

    for a in attendance:
        key = f"attendance {a['student_id']}/{a['course_code']}"
        if a["student_id"] not in sids:
            errors.append(f"{key}: unknown student")
        if a["course_code"] not in codes:
            errors.append(f"{key}: unknown course")
        elif codes[a["course_code"]]["programme"] != prog.get(a["student_id"]):
            errors.append(f"{key}: course programme differs from student programme")
        held, att = int(a["classes_held"]), int(a["classes_attended"])
        if held <= 0 or not (0 <= att <= held):
            errors.append(f"{key}: attended {att} / held {held} invalid")

    latest: dict[tuple[str, str], str] = {}
    for r in sorted(results, key=lambda r: (r["student_id"], r["course_code"], r["exam_session"], r["exam_type"])):
        key = f"results {r['student_id']}/{r['course_code']}/{r['exam_session']}/{r['exam_type']}"
        if r["student_id"] not in sids:
            errors.append(f"{key}: unknown student")
        if r["course_code"] not in codes:
            errors.append(f"{key}: unknown course")
        i, e, t, m = int(r["internal_marks"]), int(r["external_marks"]), int(r["total_marks"]), int(r["max_marks"])
        if not (0 <= i <= 40 and 0 <= e <= 60 and 0 <= t <= m):
            errors.append(f"{key}: marks out of range")
        if t != i + e:
            errors.append(f"{key}: total {t} != internal {i} + external {e}")
        passed = t >= PASS_TOTAL and e >= PASS_EXT
        if r["result"] == "PASS" and not passed:
            errors.append(f"{key}: PASS but marks below criteria")
        if r["result"] == "FAIL" and passed:
            errors.append(f"{key}: FAIL but marks satisfy criteria")
        if r["result"] in ("ABSENT", "DETAINED") and e != 0:
            errors.append(f"{key}: {r['result']} with external marks")
        if r["result"] not in ("PASS", "FAIL", "ABSENT", "DETAINED"):
            errors.append(f"{key}: bad result {r['result']}")
        if r["exam_type"] not in ("REGULAR", "SUPPLEMENTARY"):
            errors.append(f"{key}: bad exam_type")
        latest[(r["student_id"], r["course_code"])] = r["result"]

    derived = Counter(sid for (sid, _), res in latest.items() if res != "PASS")
    for s in students:
        if int(s["active_backlogs"]) != derived.get(s["student_id"], 0):
            errors.append(f"students {s['student_id']}: active_backlogs={s['active_backlogs']} but results imply {derived.get(s['student_id'], 0)}")

    # ---- informational: minimums and edge-case coverage ----
    info.append(f"students={len(students)} programmes={len(set(prog.values()))} batches={len({s['batch_year'] for s in students})} "
                f"courses={len(courses)} attendance_rows={len(attendance)} result_rows={len(results)}")
    if len(students) < 30 or len(set(prog.values())) < 2 or len({s['batch_year'] for s in students}) < 2 or len(courses) < 6:
        info.append("WARNING: below the guide's minimums (30 students, 2 programmes, 2 batches, 6 courses)")
    pct = defaultdict(list)
    for a in attendance:
        pct[a["student_id"]].append(round(100 * int(a["classes_attended"]) / int(a["classes_held"]), 2))
    flat = [p for ps in pct.values() for p in ps]
    info.append(f"attendance % exactly 80: {sum(1 for p in flat if p == 80.0)} | exactly 75: {sum(1 for p in flat if p == 75.0)} "
                f"| one class below 80 (78.0 of 50): {sum(1 for p in flat if p == 78.0)}")
    info.append(f"results: {dict(Counter(r['result'] for r in results))}; marks total 39 (just below pass): "
                f"{sum(1 for r in results if int(r['total_marks']) == 39)}")
    info.append(f"students with >=2 backlogs: {[s for s, n in derived.items() if n >= 2]}")
    info.append(f"cgpa exactly 6.0: {[s['student_id'] for s in students if float(s['cgpa']) == 6.0]} | exactly 8.5: "
                f"{[s['student_id'] for s in students if float(s['cgpa']) == 8.5]}")
    info.append(f"supplementary PASS rows: {sum(1 for r in results if r['exam_type'] == 'SUPPLEMENTARY' and r['result'] == 'PASS')}")
    return errors, info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent / "data" / "synthetic"))
    ap.add_argument("--report", default=None, help="write the report to this file as well")
    args = ap.parse_args()
    errors, info = validate(Path(args.dir))
    lines = [f"Validation of {args.dir}", ""] + info + ["", f"VIOLATIONS: {len(errors)}"] + [f"  - {e}" for e in errors[:50]]
    text = "\n".join(lines)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
