"""Утилиты для работы с рейтингами облигаций.

Этот модуль содержит функции стандартизации рейтингов и определения
позиции рейтинга в шкале. Используется в data_loader и bond_transformer.
"""

from typing import Any, Dict, List, Optional

from db_repository.utils.rating_utils import RATINGS, get_rating_index, standardize_rating


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
