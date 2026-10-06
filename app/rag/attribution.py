"""Recover missing citation labels from supporting text rather than choosing source #1."""
from __future__ import annotations

import re

from app.services.llm import _terms

_WORDS = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split(), range(21)))
_LABELS = re.compile(r"\[S\d+(?:\s*,\s*S?\d+)*\]")
_FILLER = {"according", "evidence", "stated", "states", "provided", "information", "only", "this", "these"}


def normalise_numbers(text: str) -> str:
    return re.sub(r"\b(" + "|".join(_WORDS) + r")\b", lambda match: str(_WORDS[match.group().lower()]), text, flags=re.I)


def normalise_labels(text: str) -> str:
    return _LABELS.sub(lambda match: " ".join(f"[S{number}]" for number in re.findall(r"\d+", match.group())), text)


def attribute_unlabelled_answer(answer: str, evidence: list[dict]) -> set[int]:
    """Require figure support and substantial term overlap for unlabelled model prose."""
    indexes = set()
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", answer)
    for sentence in sentences:
        cleaned = _LABELS.sub("", sentence)
        terms = set(_terms(cleaned)) - _FILLER
        if not terms:
            continue
        figures = set(re.findall(r"\b\d+(?:\.\d+)?\b", normalise_numbers(cleaned)))
        candidates = []
        for index, source in enumerate(evidence, 1):
            text = f"{source['title']} {source.get('section', '')} {source['text']}".lower()
            source_figures = set(re.findall(r"\b\d+(?:\.\d+)?\b", normalise_numbers(text)))
            if not figures <= source_figures:
                continue
            hits = sum(term.rstrip("s") in text for term in terms)
            coverage = hits / len(terms)
            if coverage >= 0.6:
                candidates.append((coverage, hits, -index, index))
        if not candidates:
            return set()
        indexes.add(max(candidates)[3])
    return indexes
