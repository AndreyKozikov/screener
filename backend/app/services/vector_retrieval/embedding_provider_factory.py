"""Factory for vector retrieval embedding providers."""

from typing import Any, Dict, Optional

from .embedding_models import (
    LOCAL_EMBEDDING_MODEL,
    OPENROUTER_BGE_M3_EMBEDDING,
    normalize_embedding_model,
)
from .embedding_service import EmbeddingService
from .openrouter_embedding_service import OpenRouterEmbeddingService

_PROVIDER_CACHE: Dict[str, Any] = {}


def get_embedding_provider(embedding_model: Optional[str] = None) -> Any:
    """Return an embedding provider compatible with RetrievalPipeline."""
    normalized = normalize_embedding_model(embedding_model)
    if normalized not in _PROVIDER_CACHE:
        if normalized == LOCAL_EMBEDDING_MODEL:
            _PROVIDER_CACHE[normalized] = EmbeddingService()
        elif normalized == OPENROUTER_BGE_M3_EMBEDDING:
            _PROVIDER_CACHE[normalized] = OpenRouterEmbeddingService()
        else:
            raise ValueError(f"Unsupported embedding_model={embedding_model!r}")
    return _PROVIDER_CACHE[normalized]
