"""Роутеры для работы с данными ключевой ставки ЦБ РФ.

Модуль содержит эндпоинты для загрузки данных из ЦБ РФ, получения данных
с фильтрацией по датам (from/till в ISO) и экспорта в Markdown.
"""

import asyncio
from datetime import date
from typing import Any, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.keyrate_service import get_keyrate_service
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/keyrate", tags=["keyrate"])


def _parse_iso_date(value: str | None, param_name: str) -> date | None:
    """Парсит строку даты в формате ISO (YYYY-MM-DD). При ошибке — HTTP 400."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name} format. Use ISO date (YYYY-MM-DD).",
        ) from None


@router.post("/load")
async def load_keyrate_data() -> dict[str, float]:
    """Загружает данные ключевой ставки с HTML страницы ЦБ РФ и сохраняет в БД.

    Returns:
        Словарь со всеми данными ключевой ставки из БД: ключ — дата YYYY-MM-DD,
        значение — ключевая ставка (float) в процентах.

    Raises:
        HTTPException: 400 при ошибке парсинга, 502 при ошибке ЦБ, 500 при прочих.
    """
    logger = get_data_update_logger()
    logger.info("[API /keyrate/load] Request received to load key rate data")
    try:
        keyrate_service = get_keyrate_service()
        logger.info("[API /keyrate/load] Starting key rate data load...")
        result = await asyncio.to_thread(keyrate_service.load_keyrate_data)
        logger.info("[API /keyrate/load] Success: Loaded %s key rate entries", len(result))
        return result
    except ValueError as exc:
        logger.error("[API /keyrate/load] ERROR: ValueError - %s", exc)
        raise HTTPException(status_code=400, detail=f"Failed to parse key rate data: {exc}") from exc
    except RuntimeError as exc:
        logger.error("[API /keyrate/load] ERROR: RuntimeError - %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("[API /keyrate/load] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load key rate data: {exc}") from exc


@router.get("/data")
async def get_keyrate_data(
    from_: str | None = Query(None, alias="from", description="Start date (ISO YYYY-MM-DD)"),
    till: str | None = Query(None, description="End date (ISO YYYY-MM-DD)"),
) -> List[dict[str, Any]]:
    """Возвращает массив записей ключевой ставки для таблицы с фильтрацией по датам.

    Query-параметры from и till в формате ISO (YYYY-MM-DD). Если не указаны —
    фильтр по соответствующей границе не применяется.

    Returns:
        Список объектов для таблицы: каждый с полями «Дата» (YYYY-MM-DD) и
        «Ключевая ставка, % годовых» (float). Сортировка по дате по убыванию.
    """
    logger = get_data_update_logger()
    logger.info("[API /keyrate/data] Request received, from=%s, till=%s", from_, till)
    try:
        from_date = _parse_iso_date(from_, "from")
        till_date = _parse_iso_date(till, "till")
        keyrate_service = get_keyrate_service()
        result = await asyncio.to_thread(
            keyrate_service.get_keyrate_list,
            from_date,
            till_date,
        )
        return [dto.model_dump(by_alias=True, mode="json") for dto in result]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[API /keyrate/data] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get key rate data: {exc!s}",
        ) from exc


@router.get("/download/markdown")
async def download_keyrate_markdown(
    from_: str | None = Query(None, alias="from", description="Start date (ISO YYYY-MM-DD)"),
    till: str | None = Query(None, description="End date (ISO YYYY-MM-DD)"),
) -> Response:
    """Скачивает данные ключевой ставки в формате Markdown за указанный диапазон дат.

    Параметры from и till в формате ISO (YYYY-MM-DD). Если не указаны —
    возвращаются все данные из БД.
    """
    logger = get_data_update_logger()
    logger.info("[API /keyrate/download/markdown] Request received, from=%s, till=%s", from_, till)
    from_date = _parse_iso_date(from_, "from")
    till_date = _parse_iso_date(till, "till")
    keyrate_service = get_keyrate_service()
    dto_list = await asyncio.to_thread(
        keyrate_service.get_keyrate_list,
        from_date,
        till_date,
    )
    if not dto_list:
        raise HTTPException(status_code=404, detail="No data found for the specified date range")
    header_cols = ["Дата", "Ключевая ставка, % годовых"]
    markdown_lines = ["# Ключевая ставка ЦБ", "", "| " + " | ".join(header_cols) + " |", "| " + " | ".join(["---"] * len(header_cols)) + " |"]
    for dto in dto_list:
        row = dto.model_dump(by_alias=True, mode="json")
        row_values = []
        for col in header_cols:
            val = row.get(col)
            if val is None:
                row_values.append("")
            elif isinstance(val, float):
                row_values.append(f"{val:.2f}")
            else:
                row_values.append(str(val))
        markdown_lines.append("| " + " | ".join(row_values) + " |")
    markdown_lines.append("")
    filename = "keyrate"
    if from_ or till:
        if from_:
            filename += f"_{from_}"
        if till:
            filename += f"_{till}"
    else:
        filename += "_all"
    filename += ".md"
    return Response(
        content="\n".join(markdown_lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
