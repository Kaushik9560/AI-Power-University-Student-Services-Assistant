"""Unit tests for the Annex A resolver (pure, no store)."""
from datetime import date

import pytest

from app.rag.loader import DocumentMetadata
from app.rag.store import RetrievedChunk
from app.rules.precedence import resolve_sources


def _c(doc_id, text, level=1, eff="2024-07-01", to=None, supersedes=(), dist=0.2, clause="", progs=(), batches="ALL"):
    m = DocumentMetadata(doc_id=doc_id, title=doc_id, authority_level=level, effective_from=eff, effective_to=to,
                         supersedes=list(supersedes), scope_programmes=list(progs), scope_batches=batches)
    return RetrievedChunk(f"{doc_id}::{clause}", text, clause, clause, None, dist, m)


TERMS = ["minimum", "attendance", "examination"]


def test_annex_a_worked_example():
    reg = _c("REG", "7.2 Minimum attendance of 75 percent for the examination", 1, "2024-07-01", clause="7.2", dist=0.1)
    cir = _c("CIR", "2.1 Minimum attendance of 80 percent for the examination", 2, "2026-08-01", supersedes=["REG#7.2"], dist=0.2)
    faq = _c("FAQ", "Minimum attendance 65 percent is enough for the examination", 4, "2026-09-15", dist=0.15)
    r = resolve_sources([reg, cir, faq], as_of=date(2026, 10, 6), question_terms=TERMS)
    assert [c.doc_id for c in r.evidence] == ["CIR", "FAQ"]
    assert any("supersedes REG#7.2" in d["reason"] or d["reason"] == "superseded by CIR" for d in r.dropped)
    assert r.conflicts and r.conflicts[0]["resolved_by"] == "authority" and not r.unresolved


def test_clause_supersession_only_hits_that_clause():
    a = _c("REG", "7.2 attendance 75 percent", 1, clause="7.2")
    b = _c("REG", "7.3 condonation 10 percent", 1, clause="7.3")
    cir = _c("CIR", "2.1 attendance 80 percent", 2, "2026-01-15", supersedes=["REG#7.2"])
    r = resolve_sources([a, b, cir], as_of=date(2026, 10, 6))
    ids = {(c.doc_id, c.clause) for c in r.evidence}
    assert ("REG", "7.3") in ids and ("REG", "7.2") not in ids


def test_level_3_cannot_supersede():
    reg = _c("REG", "attendance 75 percent for the examination", 1, clause="7.2")
    notice = _c("NOTICE", "attendance 70 percent for the examination", 3, "2026-01-01", supersedes=["REG#7.2"])
    r = resolve_sources([reg, notice], as_of=date(2026, 10, 6), question_terms=TERMS)
    assert r.evidence[0].doc_id == "REG"


def test_not_yet_effective_is_upcoming_not_evidence():
    future = _c("FUT", "attendance 90 percent", 2, "2027-01-01")
    r = resolve_sources([future], as_of=date(2026, 10, 6))
    assert r.evidence == [] and r.upcoming[0]["doc_id"] == "FUT"


def test_expired_dropped():
    r = resolve_sources([_c("OLD", "x", 1, "2019-01-01", to="2024-06-30")], as_of=date(2026, 1, 1))
    assert r.evidence == [] and r.dropped[0]["reason"] == "expired"


def test_scope_filters():
    c = _c("MBA", "rule", progs=["MBA"])
    assert resolve_sources([c], programme="B.Tech CSE").evidence == []
    assert resolve_sources([c], programme="MBA").evidence
    b = _c("NEW", "rule", batches="2024+")
    assert resolve_sources([b], batch_year=2023).evidence == []
    assert resolve_sources([b], batch_year=2025).evidence


def test_recency_resolves_same_level():
    a = _c("CIR-A", "minimum attendance 75 percent for the examination", 2, "2025-01-01")
    b = _c("CIR-B", "minimum attendance 80 percent for the examination", 2, "2026-01-01")
    r = resolve_sources([a, b], as_of=date(2026, 10, 6), question_terms=TERMS)
    assert r.evidence[0].doc_id == "CIR-B" and r.conflicts[0]["resolved_by"] == "recency"


@pytest.mark.parametrize("percentage", ["75%", "75 %", "75 percent", "75 per cent"])
def test_percentage_formats_resolve_against_lower_authority(percentage):
    regulation = _c("REG", f"Minimum attendance of {percentage} for the examination.", 1)
    handbook = _c("HANDBOOK", "Minimum attendance of 70 percent for the examination.", 4, "2026-10-07")
    result = resolve_sources([regulation, handbook], as_of=date(2026, 10, 7), question_terms=TERMS)
    assert not result.unresolved
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["resolved_by"] == "authority"
    assert result.conflicts[0]["doc_a"] == "REG"
    assert result.conflicts[0]["values_a"] == ["75percent"]


def test_unresolved_conflict_flagged():
    a = _c("CIR-A", "minimum attendance 75 percent for the examination", 2, "2026-01-01")
    b = _c("CIR-B", "minimum attendance 80 percent for the examination", 2, "2026-01-01")
    r = resolve_sources([a, b], as_of=date(2026, 10, 6), question_terms=TERMS)
    assert r.unresolved


def test_level5_never_overrides():
    reg = _c("REG", "minimum attendance 75 percent for the examination", 1)
    notes = _c("NOTES", "minimum attendance 50 percent for the examination", 5, "2026-02-01", dist=0.01)
    r = resolve_sources([reg, notes], as_of=date(2026, 10, 6), question_terms=TERMS)
    assert [c.doc_id for c in r.evidence] == ["REG"]
