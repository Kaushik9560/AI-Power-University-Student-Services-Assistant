from app.rag.attribution import attribute_unlabelled_answer, normalise_labels


def test_unlabelled_numeric_claim_uses_supporting_clause():
    evidence = [
        {"title": "Scholarships", "section": "4", "text": "The scholarship requires a 6.5 CGPA."},
        {"title": "Regulations", "section": "11.2", "text": "A minimum attendance of 75% of total classes is required for end-semester exams."},
    ]
    assert attribute_unlabelled_answer("The minimum attendance for end-semester exams is 75% of total classes.", evidence) == {2}
    assert attribute_unlabelled_answer("The minimum attendance for end-semester exams is 90% of total classes.", evidence) == set()


def test_grouped_model_labels_are_preserved():
    assert normalise_labels("A rule [S1, S3] applies.") == "A rule [S1] [S3] applies."


def test_unrelated_future_notice_does_not_qualify_policy_answer(monkeypatch):
    import time
    from app.graph.nodes import validate

    monkeypatch.setattr(validate, "write_audit", lambda state: None)
    state = {
        "question": "Does NSUT provide supplementary examinations?",
        "answer_type": "retrieved_fact",
        "answer": "There shall be no supplementary examinations. [S1]",
        "started_at": time.time(),
        "evidence": [{"doc_id": "BTECH", "title": "NSUT BTech regulations", "section": "12.3",
                      "text": "There shall be no supplementary examinations."}],
        "upcoming_changes": [{"title": "Synthetic attendance notice", "effective_from": "2026-11-01",
                              "excerpt": "The minimum attendance is 80 percent for NSUT exams."}],
    }
    result = validate.validate_and_audit(state)
    assert result["answer"] == state["answer"]
    assert result["citations"][0]["section"] == "12.3"
