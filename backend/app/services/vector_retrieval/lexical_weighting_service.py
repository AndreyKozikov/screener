"""Local sparse lexical weights for hybrid vector retrieval."""

import math
import re
from collections import Counter
from typing import Dict, Iterable, List

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")

_STOP_WORDS = {
    "а",
    "без",
    "более",
    "бы",
    "был",
    "была",
    "были",
    "было",
    "в",
    "во",
    "для",
    "до",
    "его",
    "ее",
    "если",
    "за",
    "и",
    "из",
    "или",
    "к",
    "как",
    "ко",
    "на",
    "не",
    "о",
    "об",
    "от",
    "по",
    "при",
    "с",
    "со",
    "так",
    "то",
    "у",
    "что",
    "это",
}


class LexicalWeightingService:
    """Build sparse lexical vectors compatible with RetrievalEngine dot product."""

    def __init__(self, min_token_length: int = 2):
        self.min_token_length = min_token_length

    def _tokens(self, text: str) -> Iterable[str]:
        for match in _TOKEN_RE.finditer(text.lower().replace("ё", "е")):
            token = match.group(0)
            if token in _STOP_WORDS:
                continue
            if len(token) < self.min_token_length and not token.isdigit():
                continue
            yield token

    def build(self, text: str) -> Dict[str, float]:
        """Return an L2-normalized sparse term-weight dict for one text."""
        counts = Counter(self._tokens(text))
        if not counts:
            return {}

        weights = {
            token: 1.0 + math.log(freq)
            for token, freq in counts.items()
            if freq > 0
        }
        norm = math.sqrt(sum(weight * weight for weight in weights.values()))
        if norm <= 0:
            return {}
        return {
            token: weight / norm
            for token, weight in weights.items()
        }

    def build_many(self, texts: List[str]) -> List[Dict[str, float]]:
        """Return sparse lexical weights for a list of texts."""
        return [self.build(text) for text in texts]
