"""OWNER: rules. TODO steps 3 and 4: evaluate university eligibility rules."""

from typing import Any


def evaluate(student: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """Return a structured outcome for one student and one rule."""

    del student
    return {"rule_id": rule.get("rule_id"), "passed": None, "reason": "Not implemented"}
