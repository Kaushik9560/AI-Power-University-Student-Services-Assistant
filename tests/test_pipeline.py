"""End-to-end behaviour of the six answer types, routing, precedence and security (offline)."""


def test_policy_fact_uses_superseding_circular(ask):
    s = ask("What is the minimum attendance required to appear for end-semester exams?", None)
    assert s["answer_type"] == "retrieved_fact"
    assert "80" in s["answer"]
    assert any(c["doc_id"] == "CIR-ACAD-2026-03" for c in s["citations"])
    assert "supersedes ACAD-REG-2024#7.2" in s["precedence_decision"]


def test_as_of_date_before_circular_gives_old_rule_and_mentions_upcoming(ask):
    s = ask("What is the minimum attendance required to appear for end-semester exams?", None, as_of="2025-10-01")
    assert "75" in s["answer"]
    assert all(c["doc_id"] != "CIR-ACAD-2026-03" for c in s["citations"])
    assert any(u["doc_id"] == "CIR-ACAD-2026-03" for u in s["upcoming_changes"])
    assert "takes effect on 2026-01-15" in s["answer"]


def test_expired_regulation_never_cited(ask):
    s = ask("What is the minimum attendance required to appear for end-semester exams?", None)
    assert all(c["doc_id"] != "ACAD-REG-2021" for c in s["citations"])


def test_procedure_is_grounded(ask):
    s = ask("How do I apply for the supplementary exam?", None)
    assert s["answer_type"] == "retrieved_fact"
    assert any(c["doc_id"] == "ACAD-REG-2024" and (c["section"] or "").startswith("9.2") for c in s["citations"])


def test_not_found(ask):
    s = ask("What is the scholarship for studying in Antarctica?", None)
    assert s["answer_type"] == "not_found"
    assert s["answer"] == "I could not find this information in the authorised university sources."
    assert s["citations"] == []


def test_personal_attendance_is_tool_computed(ask):
    s = ask("What is my attendance in DBMS?", "S1001")
    assert s["answer_type"] == "calculated"
    assert "82.0%" in s["answer"]
    assert [t["tool"] for t in s["tools_invoked"]] == ["get_student", "get_attendance"]
    assert s["tools_invoked"][1]["output"]["attendance_pct"] == 82.0
    assert any(r["rule_id"] == "ATT-MIN-02" for r in s["applied_rules"])


def test_supplementary_eligibility_positive_and_negative(ask):
    ok = ask("Am I eligible for the supplementary exam in Data Structures?", "S1001")
    assert ok["answer_type"] == "calculated" and ok["verdict"] is True
    assert any(r["rule_id"] == "SUPP-ELIG-01" for r in ok["applied_rules"])
    detained = ask("Am I eligible for the supplementary exam in Data Structures?", "S1002")
    assert detained["verdict"] is False and "DETAINED" in detained["explanation"]


def test_exam_eligibility_edge_cases(ask):
    at = ask("Am I eligible to appear for the end-semester exam in DBMS?", "S1005")   # exactly 80%
    below = ask("Am I eligible to appear for the end-semester exam in DBMS?", "S1006")  # 78% (one class below)
    assert at["verdict"] is True and below["verdict"] is False
    assert "condon" in below["explanation"].lower()


def test_placement_cgpa_edge(ask):
    assert ask("Am I eligible for placements?", "S1004")["verdict"] is True    # exactly 6.0
    assert ask("Am I eligible for placements?", "S1003")["verdict"] is False   # 5.8


def test_multi_step_hero(ask):
    s = ask("I failed Data Structures. If I pass the supplementary, will I be eligible for placement?", "S1001")
    assert s["answer_type"] == "calculated" and s["verdict"] is True
    tools = [t["tool"] for t in s["tools_invoked"]]
    assert "check_supplementary_eligibility" in tools and tools.count("check_placement_eligibility") == 2
    assert s["assumptions"] and "Assumptions:" in s["explanation"]
    assert {"SUPP-ELIG-01", "PLACE-CGPA-01", "PLACE-BACKLOG-01"} <= {r["rule_id"] for r in s["applied_rules"]}


def test_multi_step_multiple_backlogs_not_eligible(ask):
    s = ask("I failed Data Structures. If I pass the supplementary, will I be eligible for placement?", "S1009")
    assert s["verdict"] is False  # two other backlogs remain and CGPA 5.1


def test_conflict_flagged_same_level_same_date(ask):
    s = ask("What time do the hostel gates close?", None)
    assert s["answer_type"] == "conflict_flagged"
    assert {c["doc_id"] for c in s["citations"]} == {"CIR-HOSTEL-2026-01", "CIR-HOSTEL-2026-02"}


def test_clarification_cases(ask):
    assert ask("Am I eligible?", "S1001")["answer_type"] == "clarification_needed"
    s = ask("What is my attendance?", "S1001")
    assert s["answer_type"] == "clarification_needed" and "CS301" in s["answer"]


def test_refuses_other_student_and_requires_identity(ask):
    assert ask("Show attendance of S1002", "S1001")["answer_type"] == "refused"
    assert ask("What is the CGPA of student S1003?", "S1001")["answer_type"] == "refused"
    assert ask("What is my CGPA?", None)["answer_type"] == "refused"
    assert ask("What is my attendance in DBMS?", None)["answer_type"] == "refused"


def test_prompt_injection_document_is_data(ask, fake_store):
    from pathlib import Path
    from app.config import settings
    from app.rag.loader import load_file

    fake_store.index_document(load_file(settings.DOCUMENTS_DIR / "demo" / "UNOFFICIAL-NOTES-2026.md"))
    s = ask("What is the minimum attendance required to appear for end-semester exams?", None)
    assert "80" in s["answer"] and "50 percent" not in s["answer"]
    assert all(c["doc_id"] != "UNOFFICIAL-NOTES-2026" for c in s["citations"])
    assert any(d["doc_id"] == "UNOFFICIAL-NOTES-2026" and "level-5" in d["reason"] for d in s["dropped_sources"]) or \
        all(d["doc_id"] != "UNOFFICIAL-NOTES-2026" for d in s["sources_retrieved"])
    fake_store.delete_document("UNOFFICIAL-NOTES-2026")


def test_live_ingested_circular_changes_answer(ask, fake_store):
    from app.config import settings
    from app.rag.loader import load_file

    fake_store.index_document(load_file(settings.DOCUMENTS_DIR / "demo" / "CIR-ACAD-2026-09-JUDGE-EXAMPLE.md"))
    s = ask("How much attendance shortage can be condoned on medical grounds?", "S1001")  # batch 2024 → in scope
    assert any(c["doc_id"] == "CIR-ACAD-2026-09" for c in s["citations"])
    fake_store.delete_document("CIR-ACAD-2026-09")


def test_audit_record_complete(ask):
    from app.audit.store import read_audit

    s = ask("What is my attendance in DBMS?", "S1001")
    rec = read_audit(s["trace_id"])
    assert rec["answer_type"] == "calculated"
    assert rec["tools_invoked"][1]["tool"] == "get_attendance" and rec["tools_invoked"][1]["status"] == "ok"
    assert rec["rules_applied"] == ["ATT-MIN-02"]
    assert rec["llm_calls"] == 1 and rec["tokens"] > 0 and rec["latency_ms"] >= 0


def test_resolved_conflicting_clause_is_not_given_to_model(ask):
    s = ask("What is the minimum attendance required to appear for end-semester exams?", None)
    assert all(ev["doc_id"] != "HBK-2025" for ev in s["evidence"])
    assert any(d["reason"] == "conflicting clause overridden by precedence" for d in s["dropped_sources"])
    assert any(c["resolved_by"] == "authority" for c in s["conflicts"])


def test_missing_placement_rule_does_not_ask_model_for_verdict(ask, monkeypatch):
    from app.tools import student_tools

    monkeypatch.setattr(student_tools, "list_rules", lambda parameter: [])
    s = ask("Am I eligible for placements?", "S1001")
    assert s["answer_type"] == "not_found"
    assert s["verdict"] is None and s["llm_calls"] == 0
    assert "No rule for placement_min_cgpa" in s["explanation"]
