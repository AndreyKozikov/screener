import re
import httpx
from typing import List, Optional
from .models import Chunk, EmbeddedChunk

class EmbeddingService:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.timeout = 300.0 # Increased timeout for heavy loads

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Splits text into sentences using basic regex.
        """
        # Basic sentence splitting: split by . ! ? followed by space or newline
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _call_embedding_service(self, sentences: List[str]) -> List[List[float]]:
        """
        Calls the local microservice to get embeddings.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/embed",
                    json={"sentences": sentences}
                )
                response.raise_for_status()
                return response.json()["embeddings"]
        except Exception as e:
            print(f"Error calling local embedding service: {e}")
            return []

    def embed_chunk(self, chunk: Chunk) -> EmbeddedChunk:
        """
        Строит sentence-level embeddings для каждого чанка через локальный микросервис.
        """
        sentences = self.split_into_sentences(chunk.text)
        if not sentences:
            sentences = [chunk.text] if chunk.text.strip() else [" "]

        sentence_embeddings = self._call_embedding_service(sentences)

        return EmbeddedChunk(
            chunk=chunk,
            sentence_embeddings=sentence_embeddings
        )

    def embed_query(self, query: str) -> List[float]:
        """
        Преобразует запрос в эмбеддинг через локальный микросервис.
        """
        embeddings = self._call_embedding_service([query])
        if embeddings:
            return embeddings[0]
        return []
