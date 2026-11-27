"""Роутер API для загрузки, парсинга и получения данных ИПЦ Росстата."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from conversion_service.app.repository.files.file_storage import FileStorage
from conversion_service.app.services.ipc_service import DEFAULT_EXCEL_PATH, get_ipc_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ipc", tags=["ipc_inflation"])


@router.post(
    "/upload",
    summary="Загрузка Excel-файла ИПЦ по ссылке или с клиента, парсинг и сохранение в БД",
)
async def upload_and_parse_ipc(
    file: Optional[UploadFile] = File(
        default=None,
        description="Excel-файл (.xlsx) с данными ИПЦ",
    ),
    url: Optional[str] = Form(
        default=None,
        description="Прямая ссылка на Excel-файл ИПЦ",
    ),
) -> Dict[str, Any]:
    """Принимает ссылку или Excel-файл, парсит данные и записывает их в БД."""
    service = get_ipc_service()

    if url and url.strip():
        logger.info("[IPC ROUTER] Загрузка файла по ссылке: %s", url.strip())
        try:
            return await service.download_parse_and_save(url=url.strip())
        except Exception as exc:
            logger.error(
                "[IPC ROUTER] Ошибка при загрузке файла по ссылке: %s",
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка загрузки файла по ссылке: {exc}",
            ) from exc

    if file is None:
        raise HTTPException(
            status_code=400,
            detail="Не передан файл или ссылка на Excel-файл ИПЦ",
        )

    try:
        content = await file.read()
        target_excel_path = DEFAULT_EXCEL_PATH
        if file.filename:
            clean_filename = Path(file.filename).name
            target_excel_path = DEFAULT_EXCEL_PATH.parent / clean_filename

        await asyncio.to_thread(
            FileStorage().save_binary_file,
            target_excel_path,
            content,
        )
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


@router.post("/upload_ipc_weekly")
async def load_and_parce_ipc__weekly():
    service = get_ipc_service()
    result = await service.upload_and_parce_ipc_weekly_reports()
    return result
