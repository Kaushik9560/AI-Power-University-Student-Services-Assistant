from app.rag.loader import DocumentMetadata
from app.rag.ranking import rerank_chunks
from app.rag.store import RetrievedChunk


def chunk(id, text, distance):
    return RetrievedChunk(id, text, "", "", None, distance, DocumentMetadata(id, id))


def test_specific_clause_beats_generic_semantic_candidate():
    generic = chunk("generic", "Attendance is recorded each semester.", 0.1)
    specific = chunk("specific", "Under exceptional circumstances the Dean may grant attendance relaxation.", 0.45)
    ranked = rerank_chunks("What attendance relaxation applies under exceptional circumstances?", [generic, specific])
    assert ranked[0] is specific
    assert specific.distance == 0.45  # The semantic applicability gate remains independent.


def test_empty_query_terms_preserve_semantic_order():
    near, far = chunk("near", "One", 0.1), chunk("far", "Two", 0.8)
    assert rerank_chunks("what is it", [far, near]) == [near, far]


def test_equal_authority_preserves_reranked_evidence_order():
    from app.rules.precedence import resolve_sources

    generic = chunk("generic", "Attendance is recorded each semester.", 0.1)
    specific = chunk("specific", "Under exceptional circumstances the Dean may grant attendance relaxation.", 0.45)
    ranked = rerank_chunks("What attendance relaxation applies under exceptional circumstances?", [generic, specific])
    assert resolve_sources(ranked).evidence[0] is specific
