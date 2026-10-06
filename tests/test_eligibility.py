"""OWNER: rules. TODO step 3: cover standard and supplementary eligibility."""

from app.rules.eligibility import evaluate


def test_unimplemented_rule_is_unknown() -> None:
    outcome = evaluate({}, {"rule_id": "example"})
    assert outcome["rule_id"] == "example"
    assert outcome["passed"] is None
