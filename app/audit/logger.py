"""OWNER: audit-eval. TODO step 6: persist privacy-safe decision traces."""

from typing import Any


def record_event(event: dict[str, Any]) -> str:
    """Persist an event and return its audit identifier."""

    del event
    raise NotImplementedError("The audit-eval area owns audit persistence")
