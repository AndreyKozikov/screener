"""Роутеры для работы с данными эмитентов.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными эмитентов облигаций. Включает endpoints для получения списка эмитентов,
информации об эмитенте по SECID и массового обновления данных эмитентов.
"""

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.models import EmitentInfo
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.emitents_repository import EmitentsRepository
from app.services.data_loader import get_data_loader
from app.services.emitent_service import get_emitent_service
from app.utils.logger import get_data_update_logger
from config.paths import DATA_DIR, DB_PATH

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
            emitents_repo = EmitentsRepository(db_path=DB_PATH, data_dir=DATA_DIR)
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

    Сначала пытается получить данные из БД. Если не найдены — загружает из API MOEX
    по SECID, сохраняет в БД и возвращает результат.

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
            emitent_data = await asyncio.to_thread(
                emitent_service.fetch_emitent_from_moex, secid
            )
            if emitent_data is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Emitent data not found for SECID: {secid}",
                )
            emitents_repo = EmitentsRepository(db_path=DB_PATH, data_dir=DATA_DIR)
            secid_to_emitent_id = emitents_repo.refresh({secid: emitent_data})
            if secid_to_emitent_id:
                bonds_repo = BondsRepository(db_path=DB_PATH)
                bonds_repo.update_emitent_ids(secid_to_emitent_id)

        required_fields = emitent_service.extract_required_fields(emitent_data)
        return EmitentInfo(**required_fields)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get emitent data for SECID {secid}: {str(exc)}",
        ) from exc


def _run_emitent_pipeline_sync() -> Dict[str, Any]:
    """Синхронный пайплайн: загрузка эмитентов из API MOEX в память, сохранение в БД.

    Загружает данные из API MOEX, передаёт их в репозиторий для записи в БД,
    обновляет поле emitent_id в таблице bonds. Промежуточные файлы не используются.
    """
    logger = get_data_update_logger()
    emitent_service = get_emitent_service()
    data_loader = get_data_loader()

    bonds_details = data_loader.get_bond_details_sync()
    if not bonds_details:
        logger.warning(
            "[API /emitent/refresh] Bonds details cache is empty, loading SECIDs from database"
        )
        bonds_repo = BondsRepository(db_path=DB_PATH)
        secids = bonds_repo.get_all_secids()
        if not secids:
            logger.warning("[API /emitent/refresh] No bonds found in database, skipping")
            return {"status": "ok", "total": 0, "updated": 0, "errors": 0, "skipped": 0}
        bonds_details = {secid: {} for secid in secids}
        logger.info(
            "[API /emitent/refresh] Loaded %s SECIDs from database for emitent refresh",
            len(secids),
        )

    logger.info("=" * 80)
    logger.info(
        "[API /emitent/refresh] Starting MOEX API requests for %s bonds",
        len(bonds_details),
    )
    logger.info("=" * 80)
    
    result = emitent_service.refresh_all_emitents(bonds_details)
    api_data = result.get("data", {})
    summary = {
        "total": result.get("total", 0),
        "updated": result.get("updated", 0),
        "errors": result.get("errors", 0),
        "skipped": result.get("skipped", 0),
    }

    logger.info("=" * 80)
    logger.info(
        "[API /emitent/refresh] API requests completed: total=%s, success=%s, errors=%s, skipped=%s",
        summary["total"],
        summary["updated"],
        summary["errors"],
        summary["skipped"],
    )
    logger.info("=" * 80)

    if not api_data:
        logger.warning("[API /emitent/refresh] No data received from API, skipping database update")
        return {"status": "ok", **summary}

    logger.info("[API /emitent/refresh] Saving %s emitents to database...", len(api_data))
    emitents_repo = EmitentsRepository(db_path=DB_PATH, data_dir=DATA_DIR)
    secid_to_emitent_id = emitents_repo.refresh(api_data)

    if secid_to_emitent_id:
        logger.info("[API /emitent/refresh] Updating bonds table...")
        bonds_repo = BondsRepository(db_path=DB_PATH)
        updated_rows = bonds_repo.update_emitent_ids(secid_to_emitent_id)
        logger.info(
            "[API /emitent/refresh] ✓ Database updated: %s emitents saved, %s bonds linked",
            len(secid_to_emitent_id),
            updated_rows,
        )
    else:
        logger.warning("[API /emitent/refresh] ✗ Database update failed")

    return {"status": "ok", **summary}


@router.post("/refresh")
async def refresh_emitents_data() -> Dict[str, Any]:
    """Единый пайплайн обновления данных эмитентов с сохранением в БД.

    Загружает данные эмитентов из API MOEX в память, сохраняет в таблицы emitents
    и emitent_ratings, обновляет поле emitent_id в таблице bonds. Без промежуточных файлов.

    Returns:
        Словарь со статистикой: status, total, updated, errors, skipped.
    """
    logger = get_data_update_logger()
    logger.info("[API /emitent/refresh] Received request to refresh emitents data (API → DB)")

    try:
        result = await asyncio.to_thread(_run_emitent_pipeline_sync)
        logger.info(
            "[API /emitent/refresh] Pipeline completed: total=%s, updated=%s",
            result.get("total", 0),
            result.get("updated", 0),
        )
        return result
    except Exception as exc:
        logger.error("[API /emitent/refresh] ERROR: %s - %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh emitents: {str(exc)}",
        ) from exc
