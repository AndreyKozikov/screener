"""Роутер API для загрузки, парсинга и получения данных ИПЦ Росстата."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from conversion_service.app.models.ipc_dto import IpcLoadRequest, IpcLoadResponse
from conversion_service.app.repository.files.file_storage import FileStorage
from conversion_service.app.services.ipc_service import DEFAULT_EXCEL_PATH, get_ipc_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ipc", tags=["ipc_inflation"])


@router.post(
    "/upload",
    response_model=IpcLoadResponse,
    summary="Загрузка Excel-файла с клиента, парсинг и сохранение в JSON",
)
async def upload_and_parse_ipc(
    file: UploadFile = File(..., description="Excel-файл (.xlsx) с данными ИПЦ"),
) -> Dict[str, Any]:
    """Принимает Excel-файл от клиента, сохраняет его, парсит и записывает результат в JSON."""
    service = get_ipc_service()
    try:
        content = await file.read()
        target_excel_path = DEFAULT_EXCEL_PATH
        if file.filename:
            clean_filename = Path(file.filename).name
            target_excel_path = DEFAULT_EXCEL_PATH.parent / clean_filename

        FileStorage().save_binary_file(target_excel_path, content)
        logger.info("[IPC ROUTER] Файл %s сохранён на диск, запуск парсинга", target_excel_path)

        result = await service.parse_and_save(
            excel_path=target_excel_path
        )
        return result
    except Exception as exc:
        logger.error("[IPC ROUTER] Ошибка при обработке загруженного файла: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки загруженного файла: {exc}",
        ) from exc
