"""OWNER: rules. TODO steps 4 and 5: resolve conflicts by documented precedence."""

from typing import Any


def order_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rules in deterministic precedence order."""

    return sorted(rules, key=lambda rule: rule.get("priority", 0), reverse=True)
