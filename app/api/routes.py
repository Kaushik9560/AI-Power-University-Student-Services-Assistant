"""Shared API routes. Announce contract changes before editing."""

from fastapi import APIRouter
from app.api.schemas import AskRequest, AskResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight readiness response."""

    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Accept the stable API shape while area implementations are built."""

    return AskResponse(answer=f"Received: {request.question}")
