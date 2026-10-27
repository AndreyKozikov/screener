"""Роутеры для работы с данными эмитентов.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными эмитентов облигаций. Включает endpoints для получения списка эмитентов,
информации об эмитенте по SECID и массового обновления данных эмитентов.
"""

import asyncio
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.models import EmitentInfo
from app.repository.db.emitents_repository import EmitentsRepository
from app.services.data_loader import get_data_loader
from app.services.emitent_service import get_emitent_service
from app.utils.logger import get_data_update_logger
from config.paths import DATA_DIR

router = APIRouter(prefix="/api/emitent", tags=["emitent"])


@router.get("/list")
async def list_emitents() -> Dict[str, List[str]]:
    """Получает список всех уникальных названий эмитентов из БД.

    Сначала строит список по кэшу облигаций и маппингу secid -> emitent_title в БД.
    Если кэш пуст (например после деплоя), использует fallback: выборка уникальных
    названий напрямую из таблицы emitents.

    Returns:
        Словарь с ключом "emitents", содержащий отсортированный список уникальных
        названий эмитентов.

    Raises:
        HTTPException: Если произошла ошибка при загрузке данных (статус 500).
    """
    try:
        emitent_service = get_emitent_service()
        data_loader = get_data_loader()

        all_bonds = await data_loader.get_bonds()
        secid_to_title = emitent_service.get_secid_to_emitent_title_index()

        emitent_titles_set = set()
        for bond in all_bonds:
            secid = bond.SECID
            if secid in secid_to_title:
                emitent_title = secid_to_title[secid]
                if emitent_title and emitent_title.strip():
                    emitent_titles_set.add(emitent_title.strip())

        emitent_titles = sorted(list(emitent_titles_set))

        # Fallback: если кэш облигаций пуст (например после деплоя), список строится из БД
        if not emitent_titles:
            emitents_repo = EmitentsRepository()
            emitent_titles = emitents_repo.get_all_emitent_titles()

        return {"emitents": emitent_titles}

    except Exception as exc:
        logger = get_data_update_logger()
        logger.error("[API /emitent/list] ERROR: %s - %s", type(exc).__name__, str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get emitent list: {str(exc)}",
        ) from exc


@router.get("/{secid}", response_model=EmitentInfo)
async def get_emitent_by_secid(secid: str):
    """Получает информацию об эмитенте по SECID облигации.

    Возвращает только данные, уже сохранённые в БД. Отсутствующие данные
    не загружаются автоматически из MOEX и не сохраняются при чтении.

    Args:
        secid: Идентификатор облигации (SECID) для получения данных эмитента.

    Returns:
        Объект EmitentInfo с данными эмитента.

    Raises:
        HTTPException: Если данные эмитента не найдены (404) или произошла ошибка (500).
    """
    try:
        emitent_service = get_emitent_service()

        emitent_data = await asyncio.to_thread(emitent_service.get_emitent_by_secid, secid)
        if emitent_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Emitent data not found for SECID: {secid}",
            )

        required_fields = emitent_service.extract_required_fields(emitent_data)
        return EmitentInfo(**required_fields)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get emitent data for SECID {secid}: {str(exc)}",
        ) from exc
