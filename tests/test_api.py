"""Shared smoke tests for the API contract."""

from app.api.routes import ask, health
from app.api.schemas import AskRequest


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_ask_shape() -> None:
    response = ask(AskRequest(question="Can I register?"))
    assert response.answer
    assert response.verdict is None
