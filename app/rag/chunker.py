"""
Chunking: split by headings/clauses first (so every chunk knows its section and clause
number — needed for citations and clause-level supersession), then by a character window.

Recognised heading forms:
  "## 7.2 Minimum attendance"   (markdown)
  "7.2 Minimum attendance"      (plain PDF text, number followed by a capitalised word)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings

_MD_HEADING = re.compile(r"^(#{1,4})\s+(.*)$", re.M)
_CLAUSE_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+([A-Z][^\n]{2,80})$", re.M)
_CLAUSE_PREFIX = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\b")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    section: str        # heading text, e.g. "7.2 Minimum attendance for end-semester examination"
    clause: str         # numeric prefix, e.g. "7.2" ("" if none)
    page: int | None
    text: str
    position: int


_CLAUSE_LINE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,2})\.?\s+(?=\S)", re.M)


def _clause_label(clause: str, body: str) -> str:
    """'7.2' + a short title taken from the first sentence when it is heading-like (<= 70 chars)."""
    first = body.split("\n", 1)[0]
    title = first.split(". ", 1)[0].strip(" .")
    return f"{clause} {title}" if len(title) <= 70 else clause


def _split_clauses(body: str) -> list[tuple[str, str, bool]]:
    """Split a section body at numbered clause starts (7.1, 7.2.1 ...). Returns [(label, text, is_clause)]."""
    matches = list(_CLAUSE_LINE.finditer(body))
    if not matches:
        return [("", body, False)]
    out = []
    pre = body[: matches[0].start()].strip()
    if pre:
        out.append(("", pre, False))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[m.start():end].strip()
        rest = body[m.end():end].strip()
        out.append((_clause_label(m.group(1), rest), text, True))
    return out


def split_sections(text: str) -> list[tuple[str, str, bool]]:
    """
    Return [(section_label, body, body_already_contains_label)].
    Markdown headings and short numbered heading lines open sections; numbered clause
    paragraphs inside a section become their own sub-sections (needed for clause-level supersession).
    """
    matches = list(_MD_HEADING.finditer(text))
    title_group = 2
    if not matches:
        matches = list(_CLAUSE_HEADING.finditer(text))
        title_group = 0
    sections: list[tuple[str, str, bool]] = []
    if not matches:
        return _split_clauses(text)
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.extend(_split_clauses(preamble))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        heading = (m.group(title_group) if title_group else m.group(0)).strip()
        body = text[m.end():end].strip()
        if not body:
            # A one-line numbered clause is policy text, even without a following paragraph.
            if not title_group and _CLAUSE_PREFIX.match(heading):
                sections.append((heading, heading, True))
            continue
        parts = _split_clauses(body)
        for label, part, is_clause in parts:
            # keep the parent heading in the text so the embedding knows the topic ("7 Attendance")
            sections.append((label, f"{heading}\n{part}", True) if is_clause else (heading, part, False))
    return sections


def window(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    pieces, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        cut = text.rfind(". ", start, end)
        if cut > start + size // 2 and end < len(text):
            end = cut + 1
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]


def clause_of(heading: str) -> str:
    m = _CLAUSE_PREFIX.match(heading.strip())
    return m.group(1) if m else ""


def chunk_document(doc_id: str, pages: list[tuple[int | None, str]],
                   size: int | None = None, overlap: int | None = None) -> list[Chunk]:
    size = size or settings.CHUNK_SIZE_CHARS
    overlap = overlap or settings.CHUNK_OVERLAP_CHARS
    chunks: list[Chunk] = []
    pos = 0
    last_heading = ""
    for page_no, text in pages:
        for heading, body, inline in split_sections(text):
            if heading:
                last_heading = heading
            section = heading or last_heading  # a PDF page continuing a clause keeps the clause label
            for piece in window(body, size, overlap):
                content = piece if inline or not section else f"{section}\n{piece}"
                chunks.append(Chunk(chunk_id=f"{doc_id}::{pos}", doc_id=doc_id, section=section,
                                    clause=clause_of(section), page=page_no, text=content, position=pos))
                pos += 1
    return chunks
