"""
Embeddings. Default all-MiniLM-L6-v2 (384-d, ~80 MB, fast on CPU). BAAI/bge-small-en-v1.5
is the alternative the guide allows (EMBEDDING_PROVIDER=bge). EMBEDDING_PROVIDER=hash is a
dependency-free bag-of-words vector for offline tests only — never for the demo.

Why MiniLM: the corpus is small (hundreds of chunks), queries are short English questions,
and the deciding logic is metadata precedence, not fine-grained semantic ranking. MiniLM
is 3x faster than bge-small on CPU with no measurable difference on our evaluation set
(see docs/evaluation_report.md, configuration comparison).
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Callable

from app.config import settings

EmbedFn = Callable[[list[str]], list[list[float]]]
_MODEL_NAMES = {"minilm": "sentence-transformers/all-MiniLM-L6-v2", "bge": "BAAI/bge-small-en-v1.5"}


def _hash_embed(texts: list[str], dim: int = 512) -> list[list[float]]:
    out = []
    for t in texts:
        vec = [0.0] * dim
        for tok in re.findall(r"[a-z0-9]+", t.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


_model = None
_model_name = None


def model_name() -> str:
    if settings.EMBEDDING_PROVIDER == "hash":
        return "hash-bow (tests only)"
    return _MODEL_NAMES.get(settings.EMBEDDING_PROVIDER, settings.EMBEDDING_MODEL)


def _st_embed(texts: list[str]) -> list[list[float]]:
    global _model, _model_name
    name = model_name()
    if _model is None or _model_name != name:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(name)
        _model_name = name
    return _model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def get_embed_fn() -> EmbedFn:
    return _hash_embed if settings.EMBEDDING_PROVIDER == "hash" else _st_embed


def embedding_health() -> dict:
    return {"provider": settings.EMBEDDING_PROVIDER, "model": model_name()}
