"""Роутеры для работы с рейтингами облигаций.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с рейтингами облигаций. Включает endpoints для получения рейтинга облигации
и массового обновления рейтингов из API MOEX.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from app.services.rating_service import get_rating_service
from app.services.data_loader import get_data_loader
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/rating", tags=["rating"])
"""Роутер FastAPI для обработки запросов к API рейтингов."""




@router.get("/{secid}")
async def get_bond_rating(
    secid: str,
    boardid: str = Query(..., description="Board ID (e.g., TQCB, TQOB)")
) -> List[Dict[str, Any]]:
    """Получает данные рейтинга облигации по SECID и BOARDID только из локального кэша.
    
    Читает данные только из локального файла bonds_rating.json. Не выполняет запросы
    к API MOEX. Если данные не найдены в кэше, возвращает пустой список рейтингов.
    Для обновления рейтингов из MOEX используйте POST /api/rating/refresh.
    
    Args:
        secid: Идентификатор облигации (SECID) для получения рейтинга.
        boardid: Идентификатор торговой площадки (BOARDID), например "TQCB", "TQOB".
            Не используется в новой реализации, оставлен для совместимости.
    
    Returns:
        Список словарей с данными рейтингов, каждый словарь содержит:
        - agency_id: Идентификатор агентства рейтинга
        - agency_name_short_ru: Краткое название агентства на русском
        - rating_level_id: Идентификатор уровня рейтинга
        - rating_date: Дата присвоения рейтинга
        - rating_level_name_short_ru: Краткое название уровня рейтинга на русском
        Если рейтинг не найден в кэше, возвращается список с одной пустой записью рейтинга.
    
    Raises:
        HTTPException: Если произошла ошибка при загрузке данных из кэша
            (статус 502 или 500).
    """
    print(f"\n{'='*80}")
    print(f"[RATING] Request received")
    print(f"{'='*80}")
    print(f"[RATING] SECID: {secid}")
    print(f"[RATING] BOARDID: {boardid}")
    
    try:
        rating_service = get_rating_service()
        
        print(f"[RATING] Calling rating service (force_refresh=False - only from cache)...")
        ratings_list = await asyncio.to_thread(
            rating_service.get_rating,
            secid,
            boardid,
            False  # force_refresh=False - only return cached data, no network requests
        )
        
        # Log response details
        if ratings_list and isinstance(ratings_list, list):
            ratings_count = len(ratings_list)
            print(f"[RATING] Success: Found {ratings_count} rating entries")
            if ratings_count > 0:
                first_rating = ratings_list[0]
                print(f"[RATING] First rating entry keys: {list(first_rating.keys()) if isinstance(first_rating, dict) else 'N/A'}")
                print(f"[RATING] Sample rating: {first_rating}")
        else:
            print(f"[RATING] Warning: Response is not a list or is empty")
            print(f"[RATING] Response type: {type(ratings_list)}")
        
        print(f"[RATING] Request completed successfully")
        print(f"{'='*80}\n")
        
        return ratings_list
    except RuntimeError as exc:
        print(f"[RATING] ERROR: RuntimeError - {str(exc)}")
        print(f"[RATING] Status: 502 Bad Gateway")
        print(f"{'='*80}\n")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        print(f"[RATING] ERROR: {error_type} - {str(exc)}")
        print(f"[RATING] Status: 500 Internal Server Error")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rating for {secid}: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_ratings_data(
    force_update: bool = Query(False, description="Force update all ratings regardless of last_updated date")
):
    """Обновляет рейтинги для всех облигаций из файла bonds.json.
    
    Читает SECID и BOARDID из файла bonds.json и обновляет рейтинги для каждой
    облигации путем загрузки из API MOEX. Все обработка выполняется на бэкенде.
    
    Args:
        force_update: Если True, обновляет все рейтинги независимо от даты
            last_updated. Если False, обновляет только рейтинги, которые отсутствуют
            или устарели (старше 30 дней).
    
    Returns:
        Словарь со статистикой обновления, содержащий:
        - status: Статус операции ("ok")
        - total_bonds: Общее количество облигаций для обработки
        - updated: Количество успешно обновленных облигаций
        - errors: Количество ошибок при обновлении
        - skipped: Количество пропущенных облигаций (отсутствует SECID или BOARDID)
    
    Raises:
        HTTPException: Если произошла ошибка при обновлении данных (статус 500).
    
    Note:
        Ошибки при обновлении отдельных облигаций не прерывают процесс. Все ошибки
        логируются, и обработка продолжается для остальных облигаций. ОФЗ облигации
        (emitent_id = 1228) автоматически получают рейтинг AAA без запроса к API MOEX.
    """
    logger = get_data_update_logger()
    logger.info(f"[API /rating/refresh] Received request to refresh ratings data (force_update={force_update})")
    
    try:
        rating_service = get_rating_service()
        data_loader = get_data_loader()
        
        # Get all bonds data
        logger.info("[API /rating/refresh] Loading bonds data...")
        bonds_list = await data_loader.get_bonds()
        bonds_count = len(bonds_list)
        logger.info(f"[API /rating/refresh] Found {bonds_count} bonds to process")
        
        # Statistics
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        # Process each bond
        for idx, bond in enumerate(bonds_list):
            secid = bond.SECID
            boardid = bond.BOARDID
            
            if not secid or not boardid:
                logger.warning(f"[API /rating/refresh] Bond {idx + 1}/{bonds_count}: Skipping - missing SECID or BOARDID")
                skipped_count += 1
                continue
            
            if (idx + 1) % 100 == 0:
                logger.info(f"[API /rating/refresh] Processing bond {idx + 1}/{bonds_count}: SECID={secid}, BOARDID={boardid}")
            
            try:
                # Get rating with force_refresh based on force_update parameter
                # If force_update=True, always fetch from MOEX regardless of date
                # If force_update=False, only fetch if missing or stale
                await asyncio.to_thread(
                    rating_service.get_rating,
                    secid,
                    boardid,
                    True,  # force_refresh=True - fetch from MOEX
                    force_update  # force_update_all - ignore date check if True
                )
                updated_count += 1
            except Exception as exc:
                error_type = type(exc).__name__
                logger.error(f"[API /rating/refresh] ERROR: Failed to update rating for {secid} - {error_type}: {str(exc)}")
                error_count += 1
                # Continue processing other bonds even if one fails
                continue
        
        summary = {
            "status": "ok",
            "total_bonds": bonds_count,
            "updated": updated_count,
            "errors": error_count,
            "skipped": skipped_count
        }
        
        logger.info(f"[API /rating/refresh] Refresh completed: total={bonds_count}, updated={updated_count}, errors={error_count}, skipped={skipped_count}")
        
        return summary
        
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /rating/refresh] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh ratings: {str(exc)}"
        ) from exc

