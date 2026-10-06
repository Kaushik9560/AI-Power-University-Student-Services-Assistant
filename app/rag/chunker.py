"""Split source documents into citation-friendly heading and clause chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass

_MARKDOWN_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.M)
_CLAUSE_START = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,2})\.?\s+(?=\S)", re.M)
_CLAUSE_NUMBER = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,2})\b")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    section: str
    clause: str
    page: int | None
    text: str
    position: int


def _split_body(text: str, heading: str) -> list[tuple[str, str]]:
    matches = list(_CLAUSE_START.finditer(text))
    if not matches:
        return [(heading, text.strip())] if text.strip() else []

    parts: list[tuple[str, str]] = []
    preamble = text[:matches[0].start()].strip()
    if preamble:
        parts.append((heading, preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start():end].strip()
        clause = match.group(1)
        label = f"{heading} / {clause}" if heading else clause
        parts.append((label, body))
    return parts


def _sections(text: str) -> list[tuple[str, str]]:
    headings = list(_MARKDOWN_HEADING.finditer(text))
    if not headings:
        return _split_body(text, "")

    sections: list[tuple[str, str]] = []
    preamble = text[:headings[0].start()].strip()
    if preamble:
        sections.extend(_split_body(preamble, ""))
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        heading = match.group(2).strip()
        sections.extend(_split_body(text[match.end():end], heading))
    return sections


def _windows(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            sentence_end = text.rfind(". ", start, end)
            if sentence_end > start + size // 2:
                end = sentence_end + 1
        piece = text[start:end]
        if piece:
            pieces.append(piece)
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


def chunk_document(
    doc_id: str,
    pages: list[tuple[int | None, str]],
    size: int = 900,
    overlap: int = 150,
) -> list[Chunk]:
    """Chunk page text while retaining heading, clause, and page provenance."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be non-negative and smaller than size")

    chunks: list[Chunk] = []
    last_section = ""
    for page, text in pages:
        for section, body in _sections(text):
            if section:
                last_section = section
            else:
                section = last_section
            clause_match = _CLAUSE_NUMBER.match(section.split(" / ")[-1])
            clause = clause_match.group(1) if clause_match else ""
            for piece in _windows(body, size, overlap):
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}::{len(chunks)}",
                    doc_id=doc_id,
                    section=section,
                    clause=clause,
                    page=page,
                    text=piece,
                    position=len(chunks),
                ))
    return chunks