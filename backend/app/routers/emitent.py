"""Роутеры для работы с данными эмитентов.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными эмитентов облигаций. Включает endpoints для получения списка эмитентов,
информации об эмитенте по SECID и массового обновления данных эмитентов.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from app.models.emitent import EmitentInfo
from app.services.emitent_service import get_emitent_service
from app.services.data_loader import get_data_loader
from app.utils.logger import get_data_update_logger
from typing import Dict, Any

router = APIRouter(prefix="/api/emitent", tags=["emitent"])
"""Роутер FastAPI для обработки запросов к API эмитентов."""




@router.get("/list")
async def list_emitents() -> Dict[str, List[str]]:
    """Получает список всех уникальных названий эмитентов.
    
    Загружает все облигации из кэша DataLoader и извлекает уникальные названия
    эмитентов из кэша данных эмитентов. Возвращает отсортированный список.
    
    Returns:
        Словарь с ключом "emitents", содержащий отсортированный список уникальных
        названий эмитентов.
    
    Raises:
        HTTPException: Если произошла ошибка при загрузке данных (статус 500).
    """
    try:
        emitent_service = get_emitent_service()
        data_loader = get_data_loader()
        
        # Get all bonds
        all_bonds = await data_loader.get_bonds()
        
        # Collect unique emitent titles
        emitent_titles_set = set()
        # Access emitent data through public method (wrap in asyncio.to_thread for I/O operations)
        emitent_data_cache = await asyncio.to_thread(emitent_service._load_emitent_data)
        
        # For each bond, try to get emitent title from cache
        for bond in all_bonds:
            secid = bond.SECID
            if secid in emitent_data_cache:
                emitent_info = emitent_data_cache[secid]
                emitent_title = emitent_info.get("emitent_title")
                if emitent_title and emitent_title.strip():
                    emitent_titles_set.add(emitent_title.strip())
        
        # Sort and return
        emitent_titles = sorted(list(emitent_titles_set))
        
        return {
            "emitents": emitent_titles
        }
        
    except Exception as exc:
        logger = get_data_update_logger()
        logger.error(f"[API /emitent/list] ERROR: {type(exc).__name__} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get emitent list: {str(exc)}"
        ) from exc


@router.get("/{secid}", response_model=EmitentInfo)
async def get_emitent_by_secid(secid: str):
    """Получает информацию об эмитенте по SECID облигации.
    
    Сначала получает ISIN облигации из данных bonds.json по SECID. Затем ищет
    данные эмитента в кэше bonds_emitent.json по SECID. Если данные не найдены
    в кэше, загружает их из API MOEX по ISIN и сохраняет в bonds_emitent.json.
    
    Args:
        secid: Идентификатор облигации (SECID) для получения данных эмитента.
    
    Returns:
        Объект EmitentInfo с данными эмитента, содержащий:
        - is_traded: Флаг торговли облигацией
        - emitent_title: Название эмитента
        - emitent_inn: ИНН эмитента
        - type: Тип облигации
        - cci_rating_companies: Список рейтингов эмитента
    
    Raises:
        HTTPException: Если ISIN не найден для SECID (статус 404),
            если данные эмитента не найдены (статус 404),
            или если произошла ошибка при загрузке данных (статус 500).
    """
    try:
        # Get emitent service
        emitent_service = get_emitent_service()
        
        # Get ISIN by SECID from bonds data
        isin = await emitent_service.get_isin_by_secid(secid)
        
        if isin is None:
            raise HTTPException(
                status_code=404,
                detail=f"ISIN not found for SECID: {secid}"
            )
        
        # Get or fetch emitent data (wrap in asyncio.to_thread for I/O operations)
        emitent_data = await asyncio.to_thread(
            emitent_service.get_or_fetch_emitent,
            secid,
            isin
        )
        
        if emitent_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Emitent data not found for ISIN: {isin} (SECID: {secid})"
            )
        
        # Extract only required fields from full MOEX response
        required_fields = emitent_service.extract_required_fields(emitent_data)
        return EmitentInfo(**required_fields)
    
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get emitent data for SECID {secid}: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_emitents_data() -> Dict[str, Any]:
    """Обновляет данные эмитентов для всех облигаций из файла bonds.json.
    
    Читает SECID и ISIN из файла bonds.json и обновляет данные эмитентов для каждой
    облигации путем загрузки из API MOEX. Все обработка выполняется на бэкенде.
    
    Returns:
        Словарь со статистикой обновления, содержащий:
        - status: Статус операции ("ok")
        - total: Общее количество облигаций для обработки
        - updated: Количество успешно обновленных записей
        - errors: Количество ошибок при обновлении
        - skipped: Количество пропущенных облигаций (отсутствует ISIN)
    
    Raises:
        HTTPException: Если произошла ошибка при обновлении данных (статус 500).
    
    Note:
        Ошибки при обновлении отдельных облигаций не прерывают процесс. Все ошибки
        логируются, и обработка продолжается для остальных облигаций.
    """
    logger = get_data_update_logger()
    logger.info("[API /emitent/refresh] Received request to refresh emitents data")
    
    try:
        emitent_service = get_emitent_service()
        data_loader = get_data_loader()
        
        # Get all bonds details
        logger.info("[API /emitent/refresh] Loading bonds data...")
        bonds_details = await data_loader.get_bond_details()
        bonds_count = len(bonds_details)
        logger.info(f"[API /emitent/refresh] Found {bonds_count} bonds to process")
        
        # Refresh all emitents (wrap in asyncio.to_thread for I/O operations)
        summary = await asyncio.to_thread(
            emitent_service.refresh_all_emitents,
            bonds_details
        )
        
        logger.info(f"[API /emitent/refresh] Refresh completed: total={summary.get('total', 0)}, updated={summary.get('updated', 0)}, errors={summary.get('errors', 0)}, skipped={summary.get('skipped', 0)}")
        
        return {
            "status": "ok",
            **summary
        }
        
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /emitent/refresh] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh emitents: {str(exc)}"
        ) from exc

