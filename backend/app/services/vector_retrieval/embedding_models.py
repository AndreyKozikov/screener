"""Embedding model selection helpers for vector retrieval."""

from typing import Optional

LOCAL_EMBEDDING_MODEL = "local"
OPENROUTER_BGE_M3_EMBEDDING = "openrouter-bge-m3"
OPENROUTER_BGE_M3_MODEL_ID = "baai/bge-m3"

DEFAULT_EMBEDDING_MODEL = LOCAL_EMBEDDING_MODEL

_ALIASES = {
    "": DEFAULT_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL: LOCAL_EMBEDDING_MODEL,
    OPENROUTER_BGE_M3_EMBEDDING: OPENROUTER_BGE_M3_EMBEDDING,
}


def normalize_embedding_model(value: Optional[str]) -> str:
    """Return the canonical embedding model key used by the backend."""
    key = (value or "").strip().lower()
    try:
        return _ALIASES[key]
    except KeyError as exc:
        supported = ", ".join(sorted(k for k in _ALIASES if k))
        raise ValueError(
            f"Unsupported embedding_model={value!r}. Supported values: {supported}"
        ) from exc
