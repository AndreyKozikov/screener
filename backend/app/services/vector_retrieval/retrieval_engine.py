import numpy as np
from typing import List
from .models import Chunk, EmbeddedChunk, ScoredChunk

class RetrievalEngine:
    def retrieve(
        self,
        chunks: List[EmbeddedChunk],
        query_embeddings: List[List[float]],
        top_k: int = 30
    ) -> List[ScoredChunk]:
        """
        Выполняет многозапросный semantic search.
        chunk_score = sum(max_similarity_per_query)
        """
        scored_chunks = []
        
        for embedded_chunk in chunks:
            if not embedded_chunk.sentence_embeddings:
                continue
                
            # Convert sentence embeddings to numpy array for fast computation
            # Shape: (num_sentences, embedding_dim)
            sentence_matrix = np.array(embedded_chunk.sentence_embeddings)
            
            # Normalize sentence embeddings for cosine similarity
            sentence_norms = np.linalg.norm(sentence_matrix, axis=1, keepdims=True)
            # Avoid division by zero
            sentence_norms[sentence_norms == 0] = 1.0
            normalized_sentences = sentence_matrix / sentence_norms
            
            total_score = 0.0
            
            for q_emb in query_embeddings:
                q_vec = np.array(q_emb)
                q_norm = np.linalg.norm(q_vec)
                if q_norm == 0:
                    continue
                q_vec = q_vec / q_norm
                
                # Similarities between query and all sentences in chunk
                # Shape: (num_sentences,)
                similarities = np.dot(normalized_sentences, q_vec)
                
                # Max similarity for this query on this chunk
                max_sim = np.max(similarities)
                total_score += max_sim
                
            scored_chunks.append(ScoredChunk(
                chunk=embedded_chunk.chunk,
                score=total_score
            ))
            
        # Sort by score descending
        scored_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return scored_chunks[:top_k]
