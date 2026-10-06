"""Rule registry lookup and pure evaluation."""
from datetime import date

from app.rules.eligibility import evaluate, get_applicable_rule


def test_evaluate_operators():
    assert evaluate(">=", 80, "80") and not evaluate(">=", 79.99, "80")
    assert evaluate("<=", 0, "0") and not evaluate("<=", 1, "0")
    assert evaluate("in", "FAIL", "FAIL;ABSENT") and not evaluate("in", "DETAINED", "FAIL;ABSENT")
    assert evaluate("between", 70, "65,75") and not evaluate("between", 64.9, "65,75")
    assert evaluate("<", 3, "4") and not evaluate("<", 4, "4")


def test_rule_changes_with_date():
    old = get_applicable_rule("min_attendance_pct", "B.Tech CSE", 2024, date(2025, 10, 1))
    new = get_applicable_rule("min_attendance_pct", "B.Tech CSE", 2024, date(2026, 10, 6))
    assert (old["rule_id"], old["value"]) == ("ATT-MIN-01", "75")
    assert (new["rule_id"], new["value"], new["source_doc_id"]) == ("ATT-MIN-02", "80", "CIR-ACAD-2026-03")


def test_university_without_supplementary_exams(monkeypatch):
    from app.rules import eligibility

    rule = {"rule_id": "NSUT-SUPP-NONE", "parameter": "supplementary_regular_result",
            "operator": "in", "value": "NONE", "source_doc_id": "NSUT-BTECH-2019",
            "source_section": "12.3"}
    monkeypatch.setattr(eligibility, "get_applicable_rule", lambda *args: rule)
    verdict = eligibility.check_supplementary_eligibility(
        {"student_id": "S1001", "programme": "B.Tech CSE", "batch_year": 2024}, "CS201", date(2026, 10, 6))
    assert verdict.eligible is False
    assert "do not provide supplementary examinations" in verdict.reason
    assert verdict.source_doc_id == "NSUT-BTECH-2019"
