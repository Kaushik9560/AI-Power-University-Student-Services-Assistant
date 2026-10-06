"""Embedding providers for semantic search and dependency-light offline tests."""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable

from app.config import get_settings

EmbeddingFunction = Callable[[list[str]], list[list[float]]]
_MODELS = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "bge": "BAAI/bge-small-en-v1.5",
}
_model = None
_loaded_model_name: str | None = None


def _hash_embeddings(texts: list[str], dimensions: int = 512) -> list[list[float]]:
    vectors = []
    for text in texts:
        vector = [0.0] * dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


def model_name(provider: str | None = None) -> str:
    settings = get_settings()
    selected = (provider or settings.embedding_provider).lower()
    if selected == "hash":
        return "hash-bow (offline tests)"
    return _MODELS.get(selected, settings.embedding_model)


def _sentence_transformer_embeddings(texts: list[str], provider: str) -> list[list[float]]:
    global _model, _loaded_model_name
    name = model_name(provider)
    if _model is None or _loaded_model_name != name:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(name)
        _loaded_model_name = name
    return _model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def get_embedding_function(provider: str | None = None) -> EmbeddingFunction:
    selected = (provider or get_settings().embedding_provider).lower()
    if selected == "hash":
        return _hash_embeddings
    if selected not in _MODELS:
        raise ValueError(f"Unsupported embedding provider: {selected}")
    return lambda texts: _sentence_transformer_embeddings(texts, selected)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return normalized vectors using the configured provider."""
    return get_embedding_function()(texts)


def embedding_health() -> dict[str, str]:
    provider = get_settings().embedding_provider
    return {"provider": provider, "model": model_name(provider)}
