"""
Synthetic student data generator (guide §4.2). Fixed Annex C schema, Pydantic-enforced.

Two modes:
  python scripts/generate_students.py                 # deterministic, seed 42 (what is committed)
  python scripts/generate_students.py --llm           # ask the configured LLM (Ollama) for the
                                                      # free-text parts using data/synthetic/prompts.md,
                                                      # validate every row with Pydantic, retry on failure

In both modes the EDGE CASES are planted by code (not left to chance) and every row is
validated. Run scripts/validate_students.py afterwards; its output is committed as
data/synthetic/validation_report.txt.

Reserved for judges and never generated here: student ids S9000-S9999, course codes JDG*.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402

OUT = settings.SYNTHETIC_DIR
PASS_TOTAL, PASS_EXT, MAX_INT, MAX_EXT = 40, 21, 40, 60


# --------------------------------------------------------------------------
# Pydantic models == Annex C schema with logical constraints
# --------------------------------------------------------------------------
class Student(BaseModel):
    student_id: str = Field(pattern=r"^S\d{4}$")
    full_name: str = Field(min_length=3)
    programme: str
    batch_year: int = Field(ge=2015, le=2030)
    current_semester: int = Field(ge=1, le=10)
    cgpa: float = Field(ge=0, le=10)
    active_backlogs: int = Field(ge=0)

    @field_validator("student_id")
    @classmethod
    def _not_reserved(cls, v: str) -> str:
        if 9000 <= int(v[1:]) <= 9999:
            raise ValueError("S9000-S9999 are reserved for judges")
        return v


class Attendance(BaseModel):
    student_id: str
    course_code: str
    classes_held: int = Field(gt=0)
    classes_attended: int = Field(ge=0)

    @model_validator(mode="after")
    def _attended_le_held(self):
        if self.classes_attended > self.classes_held:
            raise ValueError("attended > held")
        return self


class Result(BaseModel):
    student_id: str
    course_code: str
    exam_session: str = Field(pattern=r"^\d{4}-(MAY|DEC|JUL|JAN)$")
    exam_type: str = Field(pattern=r"^(REGULAR|SUPPLEMENTARY)$")
    internal_marks: int = Field(ge=0, le=MAX_INT)
    external_marks: int = Field(ge=0, le=MAX_EXT)
    total_marks: int = Field(ge=0, le=100)
    max_marks: int = 100
    result: str = Field(pattern=r"^(PASS|FAIL|ABSENT|DETAINED)$")

    @model_validator(mode="after")
    def _consistent(self):
        if self.total_marks != self.internal_marks + self.external_marks:
            raise ValueError("total != internal + external")
        passed = self.total_marks >= PASS_TOTAL and self.external_marks >= PASS_EXT
        if self.result == "PASS" and not passed:
            raise ValueError("PASS but marks below pass criteria")
        if self.result == "FAIL" and passed:
            raise ValueError("FAIL but marks satisfy pass criteria")
        if self.result in ("ABSENT", "DETAINED") and self.external_marks != 0:
            raise ValueError(f"{self.result} must have external 0")
        return self


# --------------------------------------------------------------------------
# deterministic generation
# --------------------------------------------------------------------------
FIRST = ["Aarav", "Diya", "Kabir", "Ishita", "Rohan", "Ananya", "Vihaan", "Meera", "Arjun", "Saanvi", "Reyansh",
         "Nisha", "Advait", "Tara", "Dev", "Kiara", "Yash", "Pooja", "Aditya", "Riya", "Nikhil", "Sneha", "Manav",
         "Zoya", "Harsh", "Aisha", "Karan", "Priya", "Sameer", "Naina", "Rahul", "Simran", "Varun", "Mira"]
LAST = ["Sharma", "Verma", "Iyer", "Khan", "Patel", "Nair", "Singh", "Gupta", "Reddy", "Das", "Mehta", "Joshi",
        "Bose", "Kulkarni", "Chawla", "Rao", "Malhotra", "Pillai", "Saxena", "Bhat"]


def load_courses() -> list[dict]:
    with open(OUT / "courses.csv", newline="") as f:
        return [{**r, "semester": int(r["semester"]), "credits": int(r["credits"])} for r in csv.DictReader(f)]


def session_for(semester: int, batch: int) -> str:
    """Semester 1 = DEC of batch year, 2 = MAY of batch+1, 3 = DEC of batch+1 ..."""
    year = batch + (semester - 1) // 2
    return f"{year}-{'DEC' if semester % 2 == 1 else 'MAY'}"


def make_result(sid: str, code: str, session: str, rng: random.Random, outcome: str,
                exam_type: str = "REGULAR") -> Result:
    if outcome == "PASS":
        internal, external = rng.randint(24, 38), rng.randint(24, 55)
    elif outcome == "FAIL":
        internal, external = rng.randint(14, 30), rng.randint(5, 20)       # external < 21 → fail
    elif outcome == "FAIL_JUST_BELOW":                                       # total 39, external ok
        internal, external = 18, 21
    elif outcome in ("ABSENT", "DETAINED"):
        internal, external = rng.randint(10, 30), 0
    else:
        raise ValueError(outcome)
    result = "PASS" if outcome == "PASS" else ("FAIL" if outcome.startswith("FAIL") else outcome)
    return Result(student_id=sid, course_code=code, exam_session=session, exam_type=exam_type,
                  internal_marks=internal, external_marks=external, total_marks=internal + external,
                  max_marks=100, result=result)


def generate(seed: int = 42) -> tuple[list[Student], list[Attendance], list[Result]]:
    rng = random.Random(seed)
    courses = load_courses()
    by_prog: dict[str, list[dict]] = {}
    for c in courses:
        by_prog.setdefault(c["programme"], []).append(c)

    # 32 students: 2 programmes x 2 batches x 8. Batch 2023 → semester 7, batch 2024 → semester 5.
    plan = [("B.Tech CSE", 2024), ("B.Tech CSE", 2023), ("B.Tech ECE", 2024), ("B.Tech ECE", 2023)]
    students, attendance, results = [], [], []
    names = set()
    n = 1001
    for programme, batch in plan:
        for _ in range(8):
            while True:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if name not in names:
                    names.add(name)
                    break
            sem = 5 if batch == 2024 else 7
            students.append(Student(student_id=f"S{n}", full_name=name, programme=programme, batch_year=batch,
                                    current_semester=sem, cgpa=round(rng.uniform(6.2, 9.2), 2), active_backlogs=0))
            n += 1

    # ---- planted edge cases (guide §4.2) — all on CSE 2024 / 2023 students for demo clarity ----
    edge = {
        "S1001": {"cgpa": 7.21, "fail": ["CS201"], "att": {"CS301": (50, 41), "CS302": (50, 45)}},   # hero student
        "S1002": {"cgpa": 6.45, "detained": ["CS201"], "att": {"CS201": (50, 28)}},               # detained
        "S1003": {"cgpa": 5.80},                                                                  # CGPA below placement cut-off
        "S1004": {"cgpa": 6.00},                                                                  # CGPA exactly at placement cut-off
        "S1005": {"att": {"CS301": (50, 40)}},                                                    # attendance exactly at 80% threshold
        "S1006": {"att": {"CS301": (50, 39)}},                                                    # one class below the threshold
        "S1007": {"fail_just_below": ["MA201"]},                                                  # failed with total 39/100
        "S1008": {"absent": ["MA201"]},                                                           # absent result
        "S1009": {"cgpa": 5.10, "fail": ["CS201", "MA201", "CS301"]},                             # multiple backlogs (2023 batch)
        "S1010": {"cgpa": 8.50},                                                                  # CGPA exactly at merit scholarship cut-off
        "S1011": {"cleared_supp": ["CS201"]},                                                     # failed then cleared in supplementary
        "S1012": {"att": {"CS301": (40, 30)}},                                                    # exactly 75% (old threshold)
    }
    by_id = {s.student_id: s for s in students}
    for sid, spec in edge.items():
        if "cgpa" in spec:
            by_id[sid].cgpa = spec["cgpa"]

    for s in students:
        spec = edge.get(s.student_id, {})
        prog_courses = by_prog[s.programme]
        for c in prog_courses:
            code = c["course_code"]
            if c["semester"] > s.current_semester:
                continue
            # attendance for every course taken so far (current semester included)
            held = rng.choice([40, 45, 48, 50, 52, 60])
            att_pct = rng.uniform(0.78, 0.98)
            held, attended = spec.get("att", {}).get(code, (held, int(round(held * att_pct))))
            attendance.append(Attendance(student_id=s.student_id, course_code=code, classes_held=held, classes_attended=attended))
            if c["semester"] >= s.current_semester:
                continue  # current-semester courses have no result yet
            session = session_for(c["semester"], s.batch_year)
            if code in spec.get("fail", []):
                results.append(make_result(s.student_id, code, session, rng, "FAIL"))
            elif code in spec.get("fail_just_below", []):
                results.append(make_result(s.student_id, code, session, rng, "FAIL_JUST_BELOW"))
            elif code in spec.get("absent", []):
                results.append(make_result(s.student_id, code, session, rng, "ABSENT"))
            elif code in spec.get("detained", []):
                results.append(make_result(s.student_id, code, session, rng, "DETAINED"))
            elif code in spec.get("cleared_supp", []):
                results.append(make_result(s.student_id, code, session, rng, "FAIL"))
                results.append(make_result(s.student_id, code, session.replace("DEC", "JUL").replace("MAY", "JUL"),
                                           rng, "PASS", exam_type="SUPPLEMENTARY"))
            else:
                # background noise: ~8% random fails for non-edge students
                outcome = "FAIL" if (s.student_id not in edge and rng.random() < 0.08) else "PASS"
                results.append(make_result(s.student_id, code, session, rng, outcome))

    # derive active_backlogs from results so the column is always consistent
    latest: dict[tuple[str, str], str] = {}
    for r in results:
        latest[(r.student_id, r.course_code)] = r.result
    for s in students:
        s.active_backlogs = sum(1 for (sid, _), res in latest.items() if sid == s.student_id and res != "PASS")
    return students, attendance, results


# --------------------------------------------------------------------------
# LLM-assisted generation (names/CGPA/attendance distributions), Pydantic-enforced
# --------------------------------------------------------------------------
def generate_with_llm(seed: int) -> tuple[list[Student], list[Attendance], list[Result]]:
    """Ask the LLM for the student roster using prompts.md; everything else is code + validation."""
    from app.services.llm import get_llm

    prompt_text = (OUT / "prompts.md").read_text()
    system = prompt_text.split("## SYSTEM PROMPT", 1)[1].split("## USER PROMPT", 1)[0].strip()
    user = prompt_text.split("## USER PROMPT", 1)[1].split("##", 1)[0].strip()
    llm = get_llm()
    roster: list[Student] = []
    for attempt in range(3):
        resp = llm.complete(system, user, max_tokens=2500, temperature=0.4)
        text = re.sub(r"```(?:json)?|```", "", resp.text).strip()
        try:
            rows = json.loads(text)
            roster = [Student(**r) for r in rows]
            if len(roster) >= 30:
                break
            print(f"attempt {attempt + 1}: only {len(roster)} valid rows, retrying")
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            print(f"attempt {attempt + 1}: invalid output ({str(exc)[:120]}), retrying")
    if len(roster) < 30:
        print("LLM could not produce a valid roster; falling back to the deterministic generator")
        return generate(seed)
    # Reuse the deterministic attendance/results logic on the LLM roster (edge cases still planted by code).
    students, attendance, results = generate(seed)
    name_map = {s.student_id: s.full_name for s in roster}
    for s in students:
        s.full_name = name_map.get(s.student_id, s.full_name)
    return students, attendance, results


def write_csv(path: Path, rows: list[BaseModel]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].model_fields))
        w.writeheader()
        for r in rows:
            w.writerow(r.model_dump())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="use the configured LLM for the roster")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    students, attendance, results = generate_with_llm(args.seed) if args.llm else generate(args.seed)
    write_csv(out / "students.csv", students)
    write_csv(out / "attendance.csv", attendance)
    write_csv(out / "results.csv", results)
    print(f"students={len(students)} attendance={len(attendance)} results={len(results)} → {out}")


if __name__ == "__main__":
    main()
