import re
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
        return chunks
