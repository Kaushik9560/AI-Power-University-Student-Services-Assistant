"""
Source Precedence Policy — guide Annex A, implemented in CODE (never by the LLM).

Resolution order for the retrieved chunks, relative to the request's as_of_date:
  1. Applicability  effective_from <= as_of_date <= effective_to (or open), and programme/batch
                    scope covers the student. Not-yet-effective docs are excluded from the
                    answer but returned as `upcoming` so the answer can mention them.
  2. Supersession   a doc at authority level 1 or 2 that lists "DOC" or "DOC#clause" in
                    `supersedes` replaces that whole document / that clause.
  3. Authority      lower level number wins regardless of date.
  4. Recency        same level → later effective_from wins.
  5. Unresolved     same level AND same effective_from with different stated values →
                    conflict_flagged, both cited.
Level 5 content is informational only: it is kept as evidence only if nothing of higher
authority answers, and it can never produce a conflict with a higher-level document.

"Semantic similarity identifies relevant information; metadata determines whether that
information is applicable."
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.config import settings
from app.rag.loader import batch_in_scope, programme_in_scope
from app.rag.store import RetrievedChunk


@dataclass
class Resolution:
    evidence: list[RetrievedChunk]                 # applicable chunks, precedence order
    dropped: list[dict] = field(default_factory=list)   # {doc_id, chunk_id, reason}
    upcoming: list[dict] = field(default_factory=list)  # not-yet-effective docs worth mentioning
    conflicts: list[dict] = field(default_factory=list)  # noted (resolved) and unresolved
    decision: str = ""                             # one-line precedence_decision for the audit

    @property
    def unresolved(self) -> list[dict]:
        return [c for c in self.conflicts if not c.get("resolved_by")]


def _iso(d: str | None) -> date | None:
    return date.fromisoformat(d) if d else None


def _in_force(meta, as_of: date) -> tuple[bool, str]:
    ef, et = _iso(meta.effective_from), _iso(meta.effective_to)
    if ef and ef > as_of:
        return False, "not yet effective"
    if et and et < as_of:
        return False, "expired"
    return True, ""


def _clause_matches(target: str, clause: str) -> bool:
    """'7.2' supersedes chunks of clause 7.2 and 7.2.x; '7' supersedes all of 7.*"""
    return clause == target or clause.startswith(target + ".")


def resolve_sources(chunks: list[RetrievedChunk], programme: str | None = None,
                    batch_year: int | None = None, as_of: date | None = None,
                    question_terms: list[str] | None = None,
                    max_evidence: int | None = None) -> Resolution:
    as_of = as_of or date.today()
    max_evidence = max_evidence or settings.EVIDENCE_MAX_CHUNKS
    res = Resolution(evidence=[])
    notes: list[str] = []

    # 0. similarity gate — irrelevant chunks never reach the policy
    relevant: list[RetrievedChunk] = []
    for c in chunks:
        if c.distance <= settings.RETRIEVAL_MAX_DISTANCE:
            relevant.append(c)
        else:
            res.dropped.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id, "reason": f"low similarity ({c.score})"})

    # 1. applicability
    applicable: list[RetrievedChunk] = []
    seen_upcoming: set[str] = set()
    for c in relevant:
        ok, why = _in_force(c.metadata, as_of)
        if not ok:
            res.dropped.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id, "reason": why})
            if why == "not yet effective" and c.doc_id not in seen_upcoming:
                seen_upcoming.add(c.doc_id)
                res.upcoming.append({"doc_id": c.doc_id, "title": c.metadata.title,
                                     "effective_from": c.metadata.effective_from,
                                     "section": c.section, "excerpt": c.text[:200]})
            continue
        if not programme_in_scope(programme, c.metadata.scope_programmes):
            res.dropped.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id, "reason": "outside programme scope"})
            continue
        if not batch_in_scope(batch_year, c.metadata.scope_batches):
            res.dropped.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id, "reason": "outside batch scope"})
            continue
        applicable.append(c)

    # 2. explicit supersession (only level 1/2 documents may supersede)
    superseding: list[tuple[str, str, RetrievedChunk]] = []  # (target_doc, target_clause, by_chunk)
    for c in applicable:
        if c.metadata.authority_level <= 2:
            for target in c.metadata.supersedes:
                doc, _, clause = target.partition("#")
                superseding.append((doc.strip(), clause.strip(), c))
    survivors: list[RetrievedChunk] = []
    for c in applicable:
        hit = next((s for s in superseding
                    if s[0] == c.doc_id and (not s[1] or _clause_matches(s[1], c.clause))), None)
        if hit:
            label = f"{c.doc_id}#{c.clause}" if hit[1] else c.doc_id
            res.dropped.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id, "reason": f"superseded by {hit[2].doc_id}"})
            notes.append(f"{hit[2].doc_id} supersedes {label} (step 2)")
        else:
            survivors.append(c)

    # Level 5 is informational: keep it only when nothing better exists.
    if any(c.metadata.authority_level < 5 for c in survivors):
        for c in [c for c in survivors if c.metadata.authority_level == 5]:
            res.dropped.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id,
                                "reason": "level-5 content cannot override official sources"})
        survivors = [c for c in survivors if c.metadata.authority_level < 5]

    # Relevance decides WHICH applicable chunks are shown;
    # 3 + 4. authority then recency decide their ORDER and who wins a disagreement.
    selected = sorted(survivors, key=lambda c: c.rank_score, reverse=True)[:max_evidence]
    selected.sort(key=lambda c: (c.metadata.authority_level,
                                 -(_iso(c.metadata.effective_from) or date.min).toordinal(),
                                 -c.rank_score))
    res.evidence = selected

    # 5. conflict detection among the evidence
    res.conflicts = _detect_conflicts(res.evidence, question_terms or [])
    for conf in res.conflicts:
        if conf["resolved_by"]:
            notes.append(f"{conf['doc_a']} vs {conf['doc_b']}: {conf['doc_a']} prevails by {conf['resolved_by']} "
                         f"(step {conf['step']})")
        else:
            notes.append(f"{conf['doc_a']} vs {conf['doc_b']}: unresolved (step 5) → conflict_flagged")
    if res.evidence and not notes:
        top = res.evidence[0]
        notes.append(f"{top.doc_id} applies: level {top.metadata.authority_level}, "
                     f"effective {top.metadata.effective_from or 'n/a'}, in force on {as_of.isoformat()}")
    res.decision = "; ".join(notes)
    return res


# --------------------------------------------------------------------------
# conflict detection: different figures for the same topic
# --------------------------------------------------------------------------
_VALUE = re.compile(r"(\d+(?:\.\d+)?|\d{1,2}:\d{2})\s*(%|percent|per cent|cgpa|credits?|marks?|days?|pm|am|attempts?|semesters?|rupees|inr)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _topic_values(text: str, terms: list[str]) -> set[str]:
    """Values with a unit, taken only from sentences that are about the question (>=2 shared terms)."""
    out = set()
    for s in _SENTENCE.split(" ".join(text.split())):
        sl = s.lower()
        if terms and sum(1 for t in terms if t in sl) < 2:
            continue
        for m in _VALUE.finditer(s):
            out.add(f"{m.group(1)}{m.group(2).lower().replace('per cent', 'percent').replace('%', 'percent')}")
    return out


def _detect_conflicts(evidence: list[RetrievedChunk], terms: list[str]) -> list[dict]:
    conflicts: list[dict] = []
    seen: list[tuple[RetrievedChunk, set[str]]] = []
    pairs: set[tuple[str, str]] = set()
    for c in evidence:
        vals = _topic_values(c.text, terms)
        if not vals:
            continue
        for other, ovals in seen:
            if other.doc_id == c.doc_id:
                continue
            units_a = {re.sub(r"[\d.:]", "", v) for v in vals}
            units_b = {re.sub(r"[\d.:]", "", v) for v in ovals}
            if not (units_a & units_b) or (vals & ovals) or (other.doc_id, c.doc_id) in pairs:
                continue  # different kinds of numbers, they agree, or this pair is already noted
            pairs.add((other.doc_id, c.doc_id))
            a, b = other.metadata, c.metadata  # `other` ranks higher (earlier in evidence)
            if a.authority_level != b.authority_level:
                resolved, step = "authority", 3
            elif (a.effective_from or "") != (b.effective_from or ""):
                resolved, step = "recency", 4
            else:
                resolved, step = None, 5
            conflicts.append({
                "doc_a": other.doc_id, "section_a": other.section, "values_a": sorted(ovals),
                "doc_b": c.doc_id, "section_b": c.section, "values_b": sorted(vals),
                "resolved_by": resolved, "step": step,
                "note": (f"{other.doc_id} (level {a.authority_level}, effective {a.effective_from}) prevails over "
                         f"{c.doc_id} (level {b.authority_level}, effective {b.effective_from}) by {resolved}"
                         if resolved else
                         f"{other.doc_id} and {c.doc_id} have the same authority level and effective date; "
                         f"contact the issuing office"),
            })
        seen.append((c, vals))
    return conflicts
