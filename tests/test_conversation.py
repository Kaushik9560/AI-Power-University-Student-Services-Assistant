import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.audit.store import read_audit


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def send(client, question, previous=None, student="S1001", as_of="2026-10-06"):
    payload = {"question": question, "as_of_date": as_of}
    if previous:
        payload["previous_trace_id"] = previous["trace_id"]
    return client.post("/ask", json=payload,
                       headers={"X-Student-Id": student} if student else {})


def test_topic_then_course_followups_finish_eligibility(client):
    first = send(client, "Am I eligible?").json()
    assert first["answer_type"] == "clarification_needed"
    assert "End-semester exam" in first["clarification_options"]
    second = send(client, "exam eligibility", first).json()
    assert "Which course" in second["answer"]
    assert any("CS301" in choice for choice in second["clarification_options"])
    third = send(client, "end-semester", second).json()
    assert "Which course" in third["answer"]
    final = send(client, "DBMS", third).json()
    assert final["answer_type"] == "calculated" and final["verdict"] is True
    assert "CS301" in final["answer"]
    audit = read_audit(final["trace_id"])
    assert audit["original_question"] == "DBMS"
    assert audit["previous_trace_id"] == third["trace_id"]
    assert "end-semester" in audit["question"]


@pytest.mark.parametrize("question", ["exam eligibility", "end-semester", "ESE"])
def test_short_exam_topic_asks_for_course(client, question):
    result = send(client, question).json()
    assert result["answer_type"] == "clarification_needed"
    assert "Which course" in result["answer"]


def test_course_reply_completes_personal_attendance(client):
    first = send(client, "What is my attendance?").json()
    result = send(client, "DBMS", first).json()
    assert result["answer_type"] == "calculated"
    assert "82.0%" in result["answer"]
    assert next(tool for tool in result["tools_invoked"] if tool["tool"] == "get_attendance")["input"] == {
        "student_id": "S1001", "course_code": "CS301"}


@pytest.mark.parametrize("student", ["S1002", None])
def test_context_cannot_cross_accounts(client, student):
    first = send(client, "Am I eligible?").json()
    result = send(client, "DBMS", first, student=student)
    assert result.status_code == 403


def test_context_date_change_requires_new_conversation(client):
    first = send(client, "Am I eligible?").json()
    assert send(client, "exam eligibility", first, as_of="2026-11-01").status_code == 400


def test_followup_foreign_id_still_refused(client):
    first = send(client, "Am I eligible for the end-semester exam?").json()
    result = send(client, "DBMS for S1002", first).json()
    assert result["answer_type"] == "refused"
    assert result["tools_invoked"] == []


def test_new_question_replaces_pending_clarification(client):
    first = send(client, "Am I eligible?").json()
    result = send(client, "What is my CGPA?", first).json()
    assert result["answer_type"] == "calculated" and "7.21" in result["answer"]
    assert read_audit(result["trace_id"])["question"] == "What is my CGPA?"


def test_missing_context_and_missing_identity_do_not_supply_records(client):
    result = client.post("/ask", json={"question": "DBMS", "previous_trace_id": "00000000"},
                         headers={"X-Student-Id": "S1001"})
    assert result.status_code == 404
    assert send(client, "Am I eligible for the exam in DBMS?", student=None).json()["answer_type"] == "refused"
