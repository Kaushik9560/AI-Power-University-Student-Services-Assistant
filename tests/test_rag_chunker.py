"""Focused tests for heading, clause, page, and overlap preservation."""

import pytest

from app.rag.chunker import chunk_document


def test_chunks_keep_clause_and_page_provenance() -> None:
    chunks = chunk_document("POLICY", [(7, "# Attendance\n\n11.2 Minimum attendance. A student needs 75 percent.\n\n11.3 Condonation. Approval is required.")])

    assert [chunk.clause for chunk in chunks] == ["11.2", "11.3"]
    assert all(chunk.section.startswith("Attendance / ") for chunk in chunks)
    assert all(chunk.page == 7 for chunk in chunks)
    assert "75 percent" in chunks[0].text


def test_long_clause_is_windowed_with_overlap() -> None:
    text = "11.2 " + ("attendance requirement " * 30)
    chunks = chunk_document("POLICY", [(None, text)], size=100, overlap=20)

    assert len(chunks) > 1
    assert all(chunk.clause == "11.2" for chunk in chunks)
    assert chunks[0].text[-20:] == chunks[1].text[:20]
    assert [chunk.position for chunk in chunks] == list(range(len(chunks)))


def test_page_continuation_keeps_last_section_metadata() -> None:
    chunks = chunk_document("POLICY", [(4, "# Attendance\n11.2 Minimum attendance rule."),
                                       (5, "Additional details continue on this page.")])

    assert len(chunks) == 2
    assert chunks[1].section == "Attendance / 11.2"
    assert chunks[1].clause == "11.2"
    assert chunks[1].page == 5


def test_rejects_invalid_window_settings() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_document("POLICY", [(None, "text")], size=10, overlap=10)