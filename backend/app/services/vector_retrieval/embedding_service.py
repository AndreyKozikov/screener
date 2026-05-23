import re
import httpx
from typing import List, Optional, Dict, Tuple, Any
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

    def _call_embedding_service(self, sentences: List[str]) -> Dict[str, Any]:
        """
        Calls the local microservice to get hybrid embeddings (dense + sparse).
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/embed",
                    json={"sentences": sentences}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Error calling local embedding service: {e}")
            return {"dense_embeddings": [], "lexical_weights": []}

    def embed_chunk(self, chunk: Chunk) -> EmbeddedChunk:
        """
        Строит sentence-level hybrid embeddings для каждого чанка через локальный микросервис.
        """
        sentences = self.split_into_sentences(chunk.text)
        if not sentences:
            sentences = [chunk.text] if chunk.text.strip() else [" "]

        data = self._call_embedding_service(sentences)
        
        # BGE-M3 service returns 'dense_embeddings' and 'lexical_weights'
        dense_embeddings = data.get("dense_embeddings", [])
        lexical_weights = data.get("lexical_weights", [])

        return EmbeddedChunk(
            chunk=chunk,
            sentence_embeddings=dense_embeddings,
            lexical_weights=lexical_weights
        )

    def embed_query(self, query: str) -> Tuple[List[float], Dict[str, float]]:
        """
        Преобразует запрос в гибридный эмбеддинг через локальный микросервис.
        """
        data = self._call_embedding_service([query])
        
        dense = []
        sparse = {}
        
        if data.get("dense_embeddings"):
            dense = data["dense_embeddings"][0]
        if data.get("lexical_weights"):
            sparse = data["lexical_weights"][0]
            
        return dense, sparse
