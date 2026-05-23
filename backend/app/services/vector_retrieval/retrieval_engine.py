import numpy as np
from typing import List, Dict, Tuple
from .models import Chunk, EmbeddedChunk, ScoredChunk

class RetrievalEngine:
    def _compute_lexical_similarity(self, query_weights: Dict[str, float], doc_weights: Dict[str, float]) -> float:
        """
        Вычисляет сходство разреженных векторов (dot product).
        """
        score = 0.0
        # Итерируемся по весам запроса, так как они обычно короче
        for token_id, q_weight in query_weights.items():
            if token_id in doc_weights:
                score += q_weight * doc_weights[token_id]
        return score

    def retrieve(
        self,
        chunks: List[EmbeddedChunk],
        query_data: List[Tuple[List[float], Dict[str, float]]],
        top_k: int = 30,
        alpha: float = 0.5
    ) -> List[ScoredChunk]:
        """
        Выполняет многозапросный гибридный поиск (Dense + Sparse).
        chunk_score = sum(max_hybrid_similarity_per_query)
        alpha: вес dense составляющей (0.0 - только sparse, 1.0 - только dense)
        """
        scored_chunks = []
        
        for embedded_chunk in chunks:
            if not embedded_chunk.sentence_embeddings:
                continue
                
            # 1. Подготовка Dense матрицы
            sentence_matrix = np.array(embedded_chunk.sentence_embeddings)
            sentence_norms = np.linalg.norm(sentence_matrix, axis=1, keepdims=True)
            sentence_norms[sentence_norms == 0] = 1.0
            normalized_sentences = sentence_matrix / sentence_norms
            
            total_score = 0.0
            
            # 2. Цикл по запросам
            for q_dense, q_sparse in query_data:
                # --- Dense Score ---
                q_vec = np.array(q_dense)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    q_vec = q_vec / q_norm
                    dense_similarities = np.dot(normalized_sentences, q_vec)
                else:
                    dense_similarities = np.zeros(len(embedded_chunk.sentence_embeddings))
                
                # --- Sparse Score ---
                sparse_similarities = []
                for s_sparse in embedded_chunk.lexical_weights:
                    sparse_sim = self._compute_lexical_similarity(q_sparse, s_sparse)
                    sparse_similarities.append(sparse_sim)
                sparse_similarities = np.array(sparse_similarities)
                
                # --- Hybrid Combination ---
                # Комбинируем на уровне предложений и берем максимум по чанку
                hybrid_similarities = alpha * dense_similarities + (1 - alpha) * sparse_similarities
                max_sim = np.max(hybrid_similarities)
                total_score += max_sim
                
            # Representative embedding for the chunk (mean of normalized sentence embeddings)
            chunk_embedding = np.mean(normalized_sentences, axis=0)
            chunk_embedding_norm = np.linalg.norm(chunk_embedding)
            if chunk_embedding_norm > 0:
                chunk_embedding = chunk_embedding / chunk_embedding_norm

            scored_chunks.append(ScoredChunk(
                chunk=embedded_chunk.chunk,
                score=total_score,
                embedding=chunk_embedding.tolist()
            ))
            
        # Sort by score descending
        scored_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return scored_chunks[:top_k]
