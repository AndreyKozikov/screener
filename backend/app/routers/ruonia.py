"""Роутеры для работы с данными индикатора RUONIA.

Обрабатывают HTTP запросы: получение данных с фильтрами по датам (from, till),
экспорт в Markdown и обновление данных из ЦБ РФ. Параметры передаются в сервис
без обработки; вся бизнес-логика и преобразование данных — в service layer.
"""

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.models import RuoniaDataResponse
from app.services.ruonia_service import get_ruonia_service
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/ruonia", tags=["ruonia"])


@router.get("/data", response_model=RuoniaDataResponse, response_model_by_alias=True)
async def get_ruonia_data(
    date_from: Optional[str] = Query(None, description="Start date DD.MM.YYYY"),
    date_to: Optional[str] = Query(None, description="End date DD.MM.YYYY"),
) -> RuoniaDataResponse:
    """Возвращает данные RUONIA с фильтрацией по диапазону дат.

    Параметры date_from и date_to передаются в сервис без изменения.
    Если не указаны — фильтр по соответствующей границе не применяется.
    """
    logger = get_data_update_logger()
    logger.info("[API /ruonia/data] Request received, date_from=%s, date_to=%s", date_from, date_to)
    try:
        ruonia_service = get_ruonia_service()
        result = await asyncio.to_thread(
            ruonia_service.get_ruonia_data,
            date_from=date_from,
            date_to=date_to,
        )
        logger.info("[API /ruonia/data] Success: %s records", result.count)
        return result
    except RuntimeError as exc:
        logger.error("[API /ruonia/data] RuntimeError: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("[API /ruonia/data] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Failed to get RUONIA data: {exc}") from exc


@router.get("/download/markdown")
async def download_ruonia_markdown(
    date_from: Optional[str] = Query(None, description="Start date DD.MM.YYYY"),
    date_to: Optional[str] = Query(None, description="End date DD.MM.YYYY"),
) -> Response:
    """Скачивает данные RUONIA в формате Markdown.

    Параметры date_from и date_to передаются в сервис без изменения.
    """
    logger = get_data_update_logger()
    logger.info("[API /ruonia/download/markdown] Request received, date_from=%s, date_to=%s", date_from, date_to)
    try:
        ruonia_service = get_ruonia_service()
        markdown_content = await asyncio.to_thread(
            ruonia_service.export_markdown,
            date_from=date_from,
            date_to=date_to,
        )
        filename = "ruonia"
        if date_from or date_to:
            if date_from:
                filename += f"_{date_from.replace('.', '-')}"
            if date_to:
                filename += f"_{date_to.replace('.', '-')}"
        else:
            filename += "_all"
        filename += ".md"
        return Response(
            content=markdown_content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.error("[API /ruonia/download/markdown] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Failed to generate Markdown: {exc}") from exc


@router.post("/refresh")
async def refresh_ruonia_data() -> dict[str, Any]:
    """Запускает обновление данных RUONIA из ЦБ РФ (инкрементальная загрузка)."""
    logger = get_data_update_logger()
    logger.info("[API /ruonia/refresh] Received request to refresh RUONIA data")
    try:
        ruonia_service = get_ruonia_service()
        result = await asyncio.to_thread(ruonia_service.update_ruonia_data)
        logger.info("[API /ruonia/refresh] Refresh completed: %s", result)
        return result
    except Exception as exc:
        logger.error("[API /ruonia/refresh] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Failed to refresh RUONIA data: {exc}") from exc
