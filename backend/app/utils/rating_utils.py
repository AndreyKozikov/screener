"""Утилиты для работы с рейтингами облигаций.

Этот модуль содержит функции стандартизации рейтингов и определения
позиции рейтинга в шкале. Используется в data_loader и bond_transformer.
"""

import re
from typing import List, Optional


RATINGS: List[str] = [
    'AAA',
    'AA+', 'AA', 'AA-',
    'A+', 'A', 'A-',
    'BBB+', 'BBB', 'BBB-',
    'BB+', 'BB', 'BB-',
    'B+', 'B', 'B-',
    'CCC+', 'CCC', 'CCC-',
    'CC', 'C',
    'D'
]
"""Шкала рейтингов от наивысшего к наинизшему.

Список содержит все возможные рейтинги облигаций в порядке убывания качества.
Используется для определения позиции рейтинга в общей шкале.
"""


def standardize_rating(rating: Optional[str]) -> Optional[str]:
    """Стандартизирует обозначение рейтинга, удаляя русские индикаторы рынка.

    Удаляет из строки рейтинга все русские индикаторы рынка, оставляя только
    основное значение рейтинга (например, AAA, AA+, BBB-) с модификаторами (+ и -).

    Args:
        rating: Строка с рейтингом, которая может содержать русские индикаторы рынка.
            Может быть None или пустой строкой.

    Returns:
        Стандартизированная строка рейтинга или None, если входное значение
        None или пустое.
    """
    if not rating or not isinstance(rating, str):
        return None

    normalized = rating.strip()
    if not normalized:
        return None

    normalized = re.sub(r'\s*\(RU\)\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\.ru\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^ru\s*', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\|ru\|', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\|RU\|', '', normalized, flags=re.IGNORECASE)
    normalized = normalized.strip()

    return normalized if normalized else None


def get_rating_index(rating: Optional[str]) -> Optional[int]:
    """Получает индекс рейтинга в шкале рейтингов.

    Определяет позицию рейтинга в списке RATINGS. Поддерживает частичное совпадение.

    Args:
        rating: Строка с рейтингом для поиска. Может быть None или пустой строкой.

    Returns:
        Индекс рейтинга в списке RATINGS (0 для наивысшего AAA) или None,
        если рейтинг не найден.
    """
    if rating is None or not rating:
        return None
    rating_upper = rating.strip().upper()

    try:
        return RATINGS.index(rating_upper)
    except ValueError:
        pass

    for i, rating_value in enumerate(RATINGS):
        if rating_value in rating_upper:
            return i
    return None
