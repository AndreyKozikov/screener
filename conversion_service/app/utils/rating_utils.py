"""Утилиты для работы с рейтингами облигаций.

Модуль содержит функции стандартизации рейтингов и определения
позиции рейтинга в шкале. Используется в data_loader и bond_transformer.
"""

import re
from typing import Any, Dict, List, Optional


RATINGS: List[str] = [
    "AAA",
    "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
    "CCC+", "CCC", "CCC-",
    "CC", "C",
    "D",
]

RU_INDICATORS_PATTERN = re.compile(
    r"\s*\(RU\)\s*$|\.ru\s*$|^\(RU\)\s*|^ru\s*|\|ru\|",
    flags=re.IGNORECASE,
)
SF_SUFFIX_PATTERN = re.compile(r"\.SF$", flags=re.IGNORECASE)
STANDARD_RATING_PATTERN = re.compile(r"(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)([+-]?)")


def standardize_rating(rating: Optional[str]) -> Optional[str]:
    """Normalize agency-specific wrappers while preserving ``+`` and ``-``.

    Examples: ``ruBB-`` -> ``BB-``, ``BBB(RU)`` -> ``BBB``,
    ``BB+|ru|`` -> ``BB+``, and ``aaa`` -> ``AAA``.
    """
    if not isinstance(rating, str):
        return None

    normalized = rating.strip()
    if not normalized:
        return None

    previous = None
    while normalized != previous:
        previous = normalized
        normalized = RU_INDICATORS_PATTERN.sub("", normalized).strip()

    normalized = SF_SUFFIX_PATTERN.sub("", normalized).strip()
    grade_candidate = re.sub(r"\s+", "", normalized).upper()

    # Return a canonical grade only when the whole value is a recognized grade.
    # This keeps agency modifiers such as + and - meaningful and avoids turning
    # unrelated text into a plausible rating through partial matching.
    match = STANDARD_RATING_PATTERN.fullmatch(grade_candidate)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    return normalized or None


def get_rating_index(rating: Optional[str]) -> Optional[int]:
    """Return the exact position of a normalized grade in the rating scale."""
    normalized = standardize_rating(rating)
    if normalized is None:
        return None

    try:
        return RATINGS.index(normalized)
    except ValueError:
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
