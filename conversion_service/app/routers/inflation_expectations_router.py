"""Роутер API для загрузки и парсинга данных инфляционных ожиданий."""

import logging
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, File, HTTPException, UploadFile

from conversion_service.app.repository.files.file_storage import FileStorage
from conversion_service.app.services.inflation_expectations_service import (
    DEFAULT_EXCEL_PATH,
    get_inflation_expectations_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inflation-expectations", tags=["inflation_expectations"])


@router.post(
    "/upload",
    summary="Загрузка Excel-файла с клиента и парсинг данных инфляционных ожиданий",
)
async def upload_and_parse_inflation_expectations(
    file: UploadFile = File(..., description="Excel-файл (.xlsx) с данными инфляционных ожиданий"),
) -> Dict[str, Any]:
    """Принимает Excel-файл от клиента, парсит его и возвращает распарсенные данные без сохранения на диск."""
    service = get_inflation_expectations_service()
    try:
        content = await file.read()
        target_excel_path = DEFAULT_EXCEL_PATH
        if file.filename:
            clean_filename = Path(file.filename).name
            target_excel_path = DEFAULT_EXCEL_PATH.parent / clean_filename

        FileStorage().save_binary_file(target_excel_path, content)
        logger.info(
            "[INFLATION EXPECTATIONS ROUTER] Файл %s сохранён на диск, запуск парсинга",
            target_excel_path,
        )

        result = await service.parse_excel(
            excel_path=target_excel_path
        )
        return result
    except Exception as exc:
        logger.error(
            "[INFLATION EXPECTATIONS ROUTER] Ошибка при обработке загруженного файла: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки загруженного файла: {exc}",
        ) from exc