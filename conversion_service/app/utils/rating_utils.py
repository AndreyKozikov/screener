"""Утилиты для работы с рейтингами облигаций.

Этот модуль содержит функции стандартизации рейтингов и определения
позиции рейтинга в шкале. Используется в data_loader и bond_transformer.
"""

import re
from typing import Any, Dict, List, Optional


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

RU_INDICATORS_PATTERN = re.compile(
    r"\s*\(RU\)\s*$|\.ru\s*$|^ru\s*|\|ru\|",
    flags=re.IGNORECASE,
)


def standardize_rating(rating: Optional[str]) -> Optional[str]:
    """Стандартизирует обозначение рейтинга, удаляя русские индикаторы рынка."""
    if not isinstance(rating, str):
        return None

    normalized = rating.strip()
    if not normalized:
        return None

    prev = None
    while normalized != prev:
        prev = normalized
        normalized = RU_INDICATORS_PATTERN.sub("", normalized)

    normalized = normalized.strip()

    return normalized or None


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


def get_worst_rating(ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Определяет наихудший рейтинг из списка рейтингов.

    Исключает рейтинги «отозван»/«отозвано», если есть другие.
    Сначала нормализует уровень рейтинга (standardize_rating), затем ищет
    в шкале; нераспознанные рейтинги считаются наихудшими, чтобы всегда
    выбрать какой-либо рейтинг (как на фронтенде).

    Args:
        ratings_list: Список словарей с ключами rating_level_name_short_ru
            и опционально agency_name_short_ru.

    Returns:
        Словарь с наихудшим рейтингом или None.
    """
    if not ratings_list:
        return None
    non_revoked = [
        r
        for r in ratings_list
        if isinstance(r, dict)
        and (r.get("rating_level_name_short_ru") or "").lower() not in ("отозван", "отозвано")
    ]
    to_check = non_revoked if non_revoked else ratings_list
    if not to_check:
        return None
    worst_rating = None
    worst_index = -1
    # Индекс для нераспознанных рейтингов — считаем наихудшими
    unknown_index = len(RATINGS)
    for rating in to_check:
        level = (rating.get("rating_level_name_short_ru") or "").strip()
        if not level:
            continue
        level_normalized = standardize_rating(level) or level
        idx = get_rating_index(level_normalized)
        if idx is None:
            idx = unknown_index
        if idx > worst_index:
            worst_index = idx
            worst_rating = rating
    return worst_rating
