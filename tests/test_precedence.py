"""OWNER: rules. TODO steps 4 and 5: test conflicting-rule precedence."""

from app.rules.precedence import order_rules


def test_higher_priority_rule_is_first() -> None:
    rules = [{"rule_id": "general", "priority": 1}, {"rule_id": "specific", "priority": 10}]
    assert order_rules(rules)[0]["rule_id"] == "specific"
