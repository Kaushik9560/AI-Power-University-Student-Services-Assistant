"""Continue a pending clarification using a same-account, server-recorded question."""
from __future__ import annotations

import re

_TOPIC_REPLIES = (
    (r"(?:end[ -]?(?:semester|sem)(?:\s+(?:exam|exams|examination))?|exam|exams|examination|ese|mse)(?:\s+eligibility)?", "end-semester exam"),
    (r"(?:supplementary|supply|re[ -]?exam)(?:\s+(?:exam|examination))?(?:\s+eligibility)?", "supplementary exam"),
    (r"(?:placement|placements|campus\s+placement)(?:\s+eligibility)?", "placement"),
)
_NEW_QUESTION = re.compile(
    r"^(?:what(?!\s+about\b)|how|when|where|who|why|does|do|is|are|am|can|will|if|suppose|show|check|tell|give)\b", re.I)


def continue_clarification(question: str, previous: dict | None) -> str:
    """Treat short replies as missing details; a fresh question starts its own request.

    The caller must check the prior record's account and date. Identity is never supplied
    here, and all student IDs in the resulting question still pass the normal R7 guard.
    """
    if not previous or previous.get("answer_type") != "clarification_needed":
        return question
    reply = question.strip().lower().replace("–", "-").replace("—", "-").strip(" .?!")
    reply = re.sub(r"^(?:the\s+)|(?:\s+please)$", "", reply)
    for pattern, topic in _TOPIC_REPLIES:
        if re.fullmatch(pattern, reply):
            return f"{previous['question']} For {topic}."
    if len(question) <= 120 and len(question.split()) <= 12 and not _NEW_QUESTION.match(reply):
        return f"{previous['question']} {question.strip()}"
    return question
