"""Получение векторов для поиска через OpenRouter."""

import logging
import re
import time
from typing import Any, Dict, List, Tuple

from openai import APIError, OpenAI

from ..config.settings import OpenRouterSettings

OPENROUTER_BGE_M3_MODEL_ID = "baai/bge-m3"
from .lexical_weighting_service import LexicalWeightingService
from .models import Chunk, EmbeddedChunk

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _build_openrouter_headers(settings: OpenRouterSettings) -> Dict[str, str]:
    """Формирует дополнительные заголовки OpenRouter."""
    headers: Dict[str, str] = {}
    if settings.http_referer:
        headers["HTTP-Referer"] = settings.http_referer
    if settings.x_title:
        headers["X-OpenRouter-Title"] = settings.x_title
    return headers


class OpenRouterEmbeddingService:
    """Получает плотные векторы модели BGE-M3 через OpenRouter."""

    supports_sparse = True

    def __init__(self, model: str = OPENROUTER_BGE_M3_MODEL_ID, batch_size: int = 64):
        settings = OpenRouterSettings()

        self.model = model
        self.batch_size = batch_size
        self._lexical = LexicalWeightingService()
        self._headers = _build_openrouter_headers(settings)
        self._client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=settings.api_key.get_secret_value(),
        )

    def split_into_sentences(self, text: str) -> List[str]:
        """Делит текст на предложения по тем же правилам, что локальный сервис."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _embed_dense_texts(self, texts: List[str]) -> List[List[float]]:
        """Запрашивает плотные векторы порциями."""
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
                except APIError as exc:
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
        """Вычисляет плотные векторы и лексические веса предложений."""
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
        """Вычисляет плотный вектор запроса и его лексические веса."""
        vectors = self._embed_dense_texts([query])
        dense = vectors[0] if vectors else []
        sparse = self._lexical.build(query)
        return dense, sparse
