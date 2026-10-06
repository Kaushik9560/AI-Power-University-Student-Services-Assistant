"""Combine semantic candidates with BM25 term matching for short policy clauses."""
from __future__ import annotations

import math
import re
from collections import Counter

_STOP = set("a an and are as at be been by can do does for from how i in is it may me my of on or "
            "our should that the their there these this to under university nsut was what when which "
            "who will with would you your required requirement given".split())


def _tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) >= 3 and word not in _STOP]


def rerank_chunks(question: str, chunks: list) -> list:
    terms = set(_tokens(question))
    if not chunks or not terms:
        return sorted(chunks, key=lambda chunk: chunk.distance)
    documents = [Counter(_tokens(chunk.text)) for chunk in chunks]
    lengths = [sum(doc.values()) for doc in documents]
    average = sum(lengths) / len(lengths) or 1
    frequencies = {term: sum(term in doc for doc in documents) for term in terms}
    scores = []
    for doc, length in zip(documents, lengths):
        score = 0.0
        for term in terms:
            count = doc[term]
            if count:
                idf = math.log(1 + (len(documents) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
                score += idf * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * length / average))
        scores.append(score)
    maximum = max(scores) or 1
    for chunk, lexical in zip(chunks, scores):
        chunk.relevance_score = 0.55 * max(0.0, 1 - chunk.distance) + 0.45 * lexical / maximum
    return sorted(chunks, key=lambda chunk: chunk.rank_score, reverse=True)
