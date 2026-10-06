"""API boundary regressions independent of pending teammate backend implementations."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes


@pytest.fixture
def boundary(monkeypatch):
    calls = []

    def query(question, student_id, as_of, **context):
        calls.append({"question": question, "student_id": student_id, **context})
        return {"trace_id": "1234abcd", "answer": "Boundary fixture",
                "answer_type": "calculated", "as_of_date": as_of}

    monkeypatch.setattr(routes, "run_query", query)
    monkeypatch.setattr(routes, "read_audit", lambda trace: {
        "question": "Am I eligible for the end-semester exam?",
        "answer_type": "clarification_needed", "student_id": "S1001",
        "as_of_date": "2026-10-06",
    } if trace == "deadbeef" else None)
    application = FastAPI()
    application.include_router(routes.router)
    with TestClient(application) as client:
        yield client, calls


def test_identity_comes_from_header_even_with_body_id(boundary):
    client, calls = boundary
    response = client.post("/ask", json={"question": "What is my CGPA?", "student_id": "S1002"},
                           headers={"X-Student-Id": " s1001 "})
    assert response.status_code == 200
    assert calls[0]["student_id"] == "S1001"


def test_body_identity_does_not_supply_a_header(boundary):
    client, calls = boundary
    client.post("/ask", json={"question": "What is my CGPA?", "student_id": "S1001"})
    assert calls[0]["student_id"] is None


@pytest.mark.parametrize("student,date,trace,status", [
    ("S1002", "2026-10-06", "deadbeef", 403),
    (None, "2026-10-06", "deadbeef", 403),
    ("S1001", "2026-11-01", "deadbeef", 400),
    ("S1001", "2026-10-06", "00000000", 404),
])
def test_invalid_followup_never_reaches_workflow(boundary, student, date, trace, status):
    client, calls = boundary
    response = client.post("/ask", json={"question": "DBMS", "as_of_date": date,
                           "previous_trace_id": trace},
                           headers={"X-Student-Id": student} if student else {})
    assert response.status_code == status
    assert calls == []


def test_course_followup_preserves_original_input(boundary):
    client, calls = boundary
    response = client.post("/ask", json={"question": "DBMS", "as_of_date": "2026-10-06",
                           "previous_trace_id": "deadbeef"}, headers={"X-Student-Id": "S1001"})
    assert response.status_code == 200
    assert calls[0]["question"] == "Am I eligible for the end-semester exam? DBMS"
    assert calls[0]["original_question"] == "DBMS"
    assert calls[0]["previous_trace_id"] == "deadbeef"


@pytest.mark.parametrize("payload", [
    {"question": ""}, {"question": "x" * 2001},
    {"question": "test", "as_of_date": "2026-02-30"},
    {"question": "test", "previous_trace_id": "../record"},
])
def test_invalid_request_never_reaches_workflow(boundary, payload):
    client, calls = boundary
    assert client.post("/ask", json=payload).status_code == 422
    assert calls == []


def test_missing_service_returns_unavailable_instead_of_import_crash(boundary, monkeypatch):
    client, calls = boundary
    monkeypatch.setattr(routes, "run_query", lambda *args, **kwargs:
                        routes._backend_call("app.services.absent_boundary_fixture", "run_query"))
    assert client.post("/ask", json={"question": "test"}).status_code == 503
    assert calls == []


def test_health_marks_missing_components_as_degraded(boundary, monkeypatch):
    client, _ = boundary

    class Store:
        def health(self):
            return {"status": "ok", "chunks": 0, "documents": 0}

    monkeypatch.setattr(routes, "get_store", Store)
    monkeypatch.setattr(routes, "_component_health", lambda *args, **kwargs: {"status": "pending"})
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["sqlite"]["status"] == "pending"
