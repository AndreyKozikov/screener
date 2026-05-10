import re
import numpy as np
from typing import List
from .models import ScoredChunk

class RankingEngine:
    def __init__(self, length_threshold: int = 1500):
        self.length_threshold = length_threshold

    def rerank(self, chunks: List[ScoredChunk]) -> List[ScoredChunk]:
        """
        Улучшает precision без потери recall с помощью эвристик.
        """
        for sc in chunks:
            text = sc.chunk.text
            heuristic_score = 0.0
            
            # Числа (ищем группы цифр)
            if re.search(r'\d+', text):
                heuristic_score += 1.0
                
            # Процентные ставки
            if '%' in text or 'процент' in text.lower():
                heuristic_score += 2.0
                
            # Формулы (=, +, -, *, /)
            # We look for signs often used in financial formulas
            if re.search(r'[=+\-*/]', text):
                # More specific formula check: number followed by operator
                if re.search(r'\d+\s*[+\-*/=]', text) or re.search(r'[+\-*/=]\s*\d+', text):
                    heuristic_score += 2.0
                
            # Длина > threshold
            if len(text) > self.length_threshold:
                heuristic_score += 1.0
                
            # Normalize heuristic score? 
            # The embedding score is sum of cosine similarities (0 to 1 each).
            # If we have 5 queries, max score is 5.
            # Heuristics can add up to 6. This might overshadow embeddings.
            # Let's scale heuristic score down a bit or adjust weights.
            # User suggested +1, +2, +2, +1.
            sc.score += heuristic_score
            
        # Re-sort after heuristic adjustment
        chunks.sort(key=lambda x: x.score, reverse=True)
        
        # Применяем MMR для обеспечения разнообразия результатов
        return self._apply_mmr(chunks)

    def _apply_mmr(self, chunks: List[ScoredChunk], lambda_param: float = 0.5, top_k: int = 15) -> List[ScoredChunk]:
        """
        Алгоритм Maximal Marginal Relevance для переранжирования с учетом разнообразия.
        """
        if not chunks:
            return []
            
        # Проверяем наличие эмбеддингов
        if any(c.embedding is None for c in chunks[:top_k]):
            return chunks

        print(f"  [VECTOR] Applying MMR ranking (diversity filter) for {len(chunks)} chunks...", flush=True)

        selected = [chunks[0]]
        remaining = chunks[1:]
        
        selected_embs = [np.array(chunks[0].embedding)]
        
        # Мы хотим отобрать top_k наиболее релевантных и разнообразных чанков
        target_count = min(top_k, len(chunks))
        
        while len(selected) < target_count:
            mmr_scores = []
            for candidate in remaining:
                cand_emb = np.array(candidate.embedding)
                
                # Релевантность (score уже включает эмбеддинги и эвристики)
                # Нормализуем score для MMR (приблизительно, так как точный диапазон неизвестен)
                rel_score = candidate.score
                
                # Сходство с уже выбранными (максимальное из всех)
                if selected_embs:
                    # Косинусное сходство (эмбеддинги уже нормализованы в retrieval_engine)
                    sim_to_selected = max([np.dot(cand_emb, s_emb) for s_emb in selected_embs])
                else:
                    sim_to_selected = 0.0
                
                # Формула MMR: lambda * Relevance - (1 - lambda) * Similarity
                mmr_score = lambda_param * rel_score - (1 - lambda_param) * sim_to_selected
                mmr_scores.append(mmr_score)
            
            best_idx = np.argmax(mmr_scores)
            selected.append(remaining[best_idx])
            selected_embs.append(np.array(remaining[best_idx].embedding))
            remaining.pop(best_idx)
            
        # Возвращаем отобранные чанки + остальные в исходном порядке (для полноты списка)
        return selected + remaining
