"""Роутеры для работы с курсами валют.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с курсами валют от ЦБ РФ. Включает endpoints для получения курсов валют
и принудительного обновления данных.
"""

import asyncio
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional

from app.services.currency_service import get_currency_service
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/currency", tags=["currency"])
"""Роутер FastAPI для обработки запросов к API курсов валют."""




@router.get("/rates")
async def get_currency_rates(
    target_date: Optional[str] = Query(None, description="Date to get rates for (YYYY-MM-DD), defaults to today")
) -> Dict[str, Any]:
    """Получает курсы валют (EUR, USD, CNY) для указанной даты.
    
    Сначала проверяет локальный кэш. Если курсы для указанной даты отсутствуют,
    автоматически загружает их из API ЦБ РФ и сохраняет в файл. Если курсы для
    указанной даты отсутствуют или пусты, возвращает ближайшую предыдущую запись
    с непустыми курсами.
    
    Args:
        target_date: Дата для получения курсов в формате YYYY-MM-DD.
            Если не указана, используется сегодняшняя дата.
    
    Returns:
        Словарь с данными о курсах валют, содержащий:
        - date: Дата в формате YYYY-MM-DD
        - source_date: Дата из ответа API ЦБ РФ (может быть пустой строкой)
        - rates: Словарь с курсами валют для EUR, USD, CNY, где каждый курс содержит:
          - code: Код валюты
          - rate: Курс за 1 единицу валюты в рублях
          - nominal: Номинал валюты
          - original_value: Исходное значение курса из API
    
    Raises:
        HTTPException: Если формат даты некорректен (статус 400),
            если не удалось загрузить данные из API ЦБ РФ (статус 502),
            или если произошла другая ошибка (статус 500).
    """
    logger = get_data_update_logger()
    logger.info(f"[API /currency/rates] Request received")
    
    try:
        # Parse date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
                logger.info(f"[API /currency/rates] Target date: {target_date}")
            except ValueError:
                logger.error(f"[API /currency/rates] ERROR: Invalid date format: {target_date}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD"
                )
        
        currency_service = get_currency_service()
        
        logger.info(f"[API /currency/rates] Getting currency rates (force_refresh=False - check cache first)...")
        rates_data = await asyncio.to_thread(
            currency_service.get_rates,
            parsed_date,
            False  # force_refresh=False - check cache first, auto-fetch if missing
        )
        
        logger.info(f"[API /currency/rates] Success: Rates retrieved for date {rates_data.get('date')}")
        logger.info(f"[API /currency/rates] Rates count: {len(rates_data.get('rates', {}))}")
        
        return rates_data
        
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.error(f"[API /currency/rates] ERROR: RuntimeError - {str(exc)}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /currency/rates] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get currency rates: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_currency_rates(
    target_date: Optional[str] = Query(None, description="Date to refresh rates for (YYYY-MM-DD), defaults to today")
) -> Dict[str, Any]:
    """Принудительно обновляет курсы валют из API ЦБ РФ для указанной даты.
    
    Всегда загружает свежие данные из API ЦБ РФ, даже если кэшированные данные
    существуют. Сохраняет обновленные данные в файл.
    
    Args:
        target_date: Дата для обновления курсов в формате YYYY-MM-DD.
            Если не указана, используется сегодняшняя дата.
    
    Returns:
        Словарь с результатом обновления, содержащий:
        - status: Статус операции ("ok" или "error")
        - date: Дата в формате YYYY-MM-DD
        - rates_count: Количество загруженных курсов валют (при успехе)
        - error: Сообщение об ошибке (при ошибке)
        - updated: Флаг успешного обновления (True или False)
    
    Raises:
        HTTPException: Если формат даты некорректен (статус 400)
            или если произошла ошибка при обновлении (статус 500).
    """
    logger = get_data_update_logger()
    logger.info(f"[API /currency/refresh] Received request to refresh currency rates")
    
    try:
        # Parse date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
                logger.info(f"[API /currency/refresh] Target date: {target_date}")
            except ValueError:
                logger.error(f"[API /currency/refresh] ERROR: Invalid date format: {target_date}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD"
                )
        
        currency_service = get_currency_service()
        
        logger.info(f"[API /currency/refresh] Refreshing currency rates...")
        result = await asyncio.to_thread(
            currency_service.refresh_rates,
            parsed_date
        )
        
        logger.info(f"[API /currency/refresh] Refresh completed: {result}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /currency/refresh] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh currency rates: {str(exc)}"
        ) from exc

