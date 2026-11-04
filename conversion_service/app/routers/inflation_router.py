"""Роутер API для загрузки и парсинга данных инфляционных ожиданий."""

import logging
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, File, HTTPException, UploadFile

from conversion_service.app.models.inflation_dto import InflationLoadByUrlRequest
from conversion_service.app.repository.files.file_storage import FileStorage
from conversion_service.app.services.inflation_service import (
    DEFAULT_EXCEL_PATH,
    get_inflation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inflations", tags=["inflations"])


def _handle_processing_error(exc: Exception) -> None:
    """Логирует и оборачивает ошибку обработки в HTTPException."""
    logger.error("[INFLATION ROUTER] Ошибка при обработке файла: %s", exc, exc_info=True)
    raise HTTPException(
        status_code=500,
        detail=f"Ошибка обработки файла: {exc}",
    ) from exc


@router.post(
    "/upload",
    summary="Загрузка Excel-файла с клиента и парсинг данных инфляционных ожиданий",
)
async def upload_and_parse_inflation_expectations(
    file: UploadFile = File(..., description="Excel-файл (.xlsx) с данными инфляционных ожиданий"),
) -> Dict[str, Any]:
    """Принимает Excel-файл от клиента, парсит его и возвращает распарсенные данные без сохранения на диск."""
    service = get_inflation_service()
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
        _handle_processing_error(exc)

@router.post(
    "/upload_by_url",
    summary="Скачивание Excel-файла инфляционных ожиданий по URL, парсинг и удаление скачанного файла",
)
async def parse_inflation_expectations_by_url(
    request: InflationLoadByUrlRequest,
) -> Dict[str, Any]:
    """Принимает URL на Excel-файл, скачивает его, парсит и после успешной обработки удаляет скачанный файл."""
    service = get_inflation_service()
    try:
        result = await service.download_and_parse_excel(url=request.url)
        return result
    except Exception as exc:
        _handle_processing_error(exc)

@router.post("/upload_inflation_data")
async def upload_and_parse_inflation_data(
        file: UploadFile = File(..., description="Excel-файл (.xlsx) с данными по инфляции"),
):
    service = get_inflation_service()
    try:
        content = await file.read()
        target_excel_path = DEFAULT_EXCEL_PATH
        if file.filename:
            clean_filename = Path(file.filename).name
            target_excel_path = DEFAULT_EXCEL_PATH.parent / clean_filename

        FileStorage().save_binary_file(target_excel_path, content)
        logger.info(
            "[INFLATION DATA ROUTER] Файл %s сохранён на диск, запуск парсинга",
            target_excel_path,
        )

        result = await service.parse_est_infl(
            excel_path=target_excel_path
        )
        return result
    except Exception as exc:
        _handle_processing_error(exc)

@router.post("/upload_inflation_data_by_url")
async def parse_inflation_data_by_url(
        request: InflationLoadByUrlRequest,
):
    """Принимает URL на Excel-файл, скачивает его, парсит и после успешной обработки удаляет скачанный файл."""
    service = get_inflation_service()
    try:
        result = await service.download_and_parse_est_infl(url=request.url)
        return result
    except Exception as exc:
        _handle_processing_error(exc)