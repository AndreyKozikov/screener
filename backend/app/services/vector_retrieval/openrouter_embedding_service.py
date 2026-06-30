"""OpenRouter-backed embedding provider for vector retrieval."""

import logging
import re
import time
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from config.settings import settings

from .embedding_models import OPENROUTER_BGE_M3_MODEL_ID
from .lexical_weighting_service import LexicalWeightingService
from .models import Chunk, EmbeddedChunk

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _build_openrouter_headers() -> Dict[str, str]:
    """Build optional OpenRouter attribution headers."""
    headers: Dict[str, str] = {}
    if settings.OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = settings.OPENROUTER_HTTP_REFERER
    if settings.OPENROUTER_X_TITLE:
        headers["X-OpenRouter-Title"] = settings.OPENROUTER_X_TITLE
    return headers


class OpenRouterEmbeddingService:
    """Hybrid embedding provider using baai/bge-m3 dense vectors via OpenRouter."""

    supports_sparse = True

    def __init__(self, model: str = OPENROUTER_BGE_M3_MODEL_ID, batch_size: int = 64):
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY не задан в настройках бэкенда")

        self.model = model
        self.batch_size = batch_size
        self._lexical = LexicalWeightingService()
        self._headers = _build_openrouter_headers()
        self._client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
        )

    def split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences, matching the local embedding provider behavior."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _embed_dense_texts(self, texts: List[str]) -> List[List[float]]:
        """Request dense embeddings from OpenRouter in batches."""
        if not texts:
            return []

        vectors: List[List[float]] = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            
            max_retries = 5
            backoff = 1.0
            response = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    request_args: Dict[str, Any] = {
                        "model": self.model,
                        "input": batch,
                        "encoding_format": "float",
                    }
                    if self._headers:
                        request_args["extra_headers"] = self._headers
                    response = self._client.embeddings.create(**request_args)
                    break
                except Exception as exc:
                    if attempt == max_retries:
                        logger.error(
                            "Ошибка вызова OpenRouter Embeddings API после %d попыток: %s",
                            max_retries,
                            exc,
                        )
                        raise RuntimeError(
                            f"Ошибка вызова OpenRouter Embeddings API после {max_retries} попыток: {exc}"
                        ) from exc
                    
                    logger.warning(
                        "Попытка %d/%d вызова OpenRouter Embeddings API не удалась: %s. Ожидание %.1f сек...",
                        attempt,
                        max_retries,
                        exc,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2.0

            if response is None or not hasattr(response, "data"):
                raise RuntimeError("Получен пустой ответ от OpenRouter Embeddings API")

            for item in response.data:
                if getattr(item, "embedding", None) is None:
                    raise RuntimeError("Один из объектов ответа OpenRouter не содержит вектор эмбеддинга")
                vectors.append(item.embedding)

        if len(vectors) != len(texts):
            raise RuntimeError(
                "OpenRouter Embeddings API вернул неожиданное количество векторов: "
                f"{len(vectors)} вместо {len(texts)}"
            )
        return vectors

    def embed_chunk(self, chunk: Chunk) -> EmbeddedChunk:
        """Build sentence-level dense and sparse embeddings for a chunk."""
        sentences = self.split_into_sentences(chunk.text)
        if not sentences:
            sentences = [chunk.text] if chunk.text.strip() else [" "]

        dense_embeddings = self._embed_dense_texts(sentences)
        lexical_weights = self._lexical.build_many(sentences)
        return EmbeddedChunk(
            chunk=chunk,
            sentence_embeddings=dense_embeddings,
            lexical_weights=lexical_weights,
        )

    def embed_query(self, query: str) -> Tuple[List[float], Dict[str, float]]:
        """Build dense and sparse embeddings for a search query."""
        vectors = self._embed_dense_texts([query])
        dense = vectors[0] if vectors else []
        sparse = self._lexical.build(query)
        return dense, sparse
