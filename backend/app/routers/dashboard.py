"""Роутеры для данных главной страницы (dashboard).

Эндпоинт отдаёт единым ответом курсы валют, ставку RUONIA и ключевую ставку
для плашки на центральной странице фронтенда.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.models import MacroRatesDTO
from app.services.dashboard_rates_service import get_dashboard_rates
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/rates", response_model=MacroRatesDTO)
async def get_dashboard_rates_endpoint() -> MacroRatesDTO:
    """Возвращает данные для плашки на главной: курсы валют, RUONIA и ключевая ставка.

    Один запрос заменяет три отдельных (currency/rates, ruonia/data, keyrate/data)
    для быстрой загрузки главной страницы. Фронтенд отображает данные без преобразований.

    Returns:
        MacroRatesDTO: date, source_date, rates (EUR, USD, CNY), ruonia_rate, key_rate.

    Raises:
        HTTPException: 502 при недоступности сервисов, 500 при прочих ошибках.
    """
    logger = get_data_update_logger()
    logger.info("[API /dashboard/rates] Request received")
    try:
        result = await asyncio.to_thread(get_dashboard_rates)
        logger.info("[API /dashboard/rates] Success")
        return result
    except RuntimeError as exc:
        logger.error("[API /dashboard/rates] RuntimeError: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[API /dashboard/rates] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard rates: {exc!s}",
        ) from exc
