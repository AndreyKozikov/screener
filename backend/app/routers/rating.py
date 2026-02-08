"""Роутеры для работы с рейтингами облигаций.

Содержит endpoints для получения рейтинга облигации из БД и массового
обновления рейтингов из API MOEX с сохранением в bond_ratings.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List

from app.services.bond_ratings_pipeline_service import BondRatingsPipelineService
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH

router = APIRouter(prefix="/api/rating", tags=["rating"])

_pipeline_service: BondRatingsPipelineService | None = None


def get_pipeline_service() -> BondRatingsPipelineService:
    """Возвращает экземпляр BondRatingsPipelineService."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = BondRatingsPipelineService(db_path=DB_PATH)
    return _pipeline_service


def _format_rating_for_api(r: Dict[str, Any]) -> Dict[str, Any]:
    """Форматирует запись рейтинга для ответа API (совместимость с фронтендом)."""
    return {
        "agency_id": r.get("agency_id", 0),
        "agency_name_short_ru": r.get("agency_name_short_ru", ""),
        "rating_level_id": 0,
        "rating_date": r.get("rating_date", ""),
        "rating_level_name_short_ru": r.get("rating_level_name", ""),
    }


@router.get("/{secid}")
async def get_bond_rating(
    secid: str,
    boardid: str = Query(..., description="Board ID (e.g., TQCB, TQOB)"),
) -> List[Dict[str, Any]]:
    """Получает данные рейтинга облигации по SECID из БД.

    Читает данные из таблицы bond_ratings. Если рейтинги не найдены,
    возвращает список с одной пустой записью для совместимости.

    Args:
        secid: Идентификатор облигации (SECID).
        boardid: Идентификатор торговой площадки. Оставлен для совместимости.

    Returns:
        Список словарей с полями agency_id, agency_name_short_ru,
        rating_level_id, rating_date, rating_level_name_short_ru.
    """
    try:
        service = get_pipeline_service()
        ratings = service.get_ratings_by_secid(secid)
        if not ratings:
            return [
                {
                    "agency_id": 0,
                    "agency_name_short_ru": "",
                    "rating_level_id": 0,
                    "rating_date": "",
                    "rating_level_name_short_ru": "",
                }
            ]
        return [_format_rating_for_api(r) for r in ratings]
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rating for {secid}: {str(exc)}",
        ) from exc


@router.post("/refresh")
async def refresh_ratings_data(
    force_update: bool = Query(
        False,
        description="Force update all ratings (reserved for future use)",
    ),
) -> Dict[str, Any]:
    """Обновляет рейтинги облигаций из API MOEX и сохраняет в bond_ratings.

    Извлекает облигации из БД, запрашивает рейтинги из MOEX и сохраняет
    в таблицу bond_ratings. Параметр force_update оставлен для совместимости.

    Returns:
        Словарь: status, total_bonds, updated, errors, skipped.
    """
    logger = get_data_update_logger()
    logger.info("[API /rating/refresh] Received request to refresh ratings")
    _ = force_update
    try:
        service = get_pipeline_service()
        result = service.run_pipeline()
        summary = {
            "status": "ok",
            "total_bonds": result["total_bonds"],
            "updated": result["updated"],
            "errors": result["errors"],
            "skipped": result["skipped"],
        }
        logger.info(
            "[API /rating/refresh] Refresh completed: %s",
            summary,
        )
        return summary
    except Exception as exc:
        logger.exception("[API /rating/refresh] ERROR: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh ratings: {str(exc)}",
        ) from exc
