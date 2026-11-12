"""Роутеры для получения метаданных приложения.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов на получение
метаданных приложения, включая маппинги колонок, описания полей и доступные
опции фильтров.
"""

from fastapi import APIRouter
from typing import Dict, List
import asyncio

from app.models import DescribeDTO
from app.repository.db.describe_repository import DescribeRepository
from app.services.data_loader import get_data_loader

router = APIRouter(prefix="/api", tags=["metadata"])
"""Роутер FastAPI для обработки запросов к API метаданных."""


@router.get("/columns", response_model=Dict[str, str])
async def get_columns():
    """Получает маппинг названий колонок (английские имена полей на русские отображаемые имена).
    
    Загружает маппинг из файла columns.json и возвращает словарь для преобразования
    английских названий полей в русские отображаемые имена колонок.
    
    Returns:
        Словарь, где ключ - английское имя поля (например, "SECID"),
        значение - русское отображаемое имя колонки (например, "Код инструмента").
        Данные загружаются из секций securities, marketdata и marketdata_yields
        файла columns.json.
    """
    loader = get_data_loader()
    return await loader.get_column_mapping()


@router.get("/descriptions", response_model=DescribeDTO)
async def get_descriptions() -> DescribeDTO:
    """Получает описания полей из БД (таблица describe_fields).

    Возвращает структуру секция -> поле -> описание для подсказок на фронтенде.
    Совместим с прежним форматом ответа (describe.json).

    Returns:
        DescribeDTO с полями securities и marketdata (словари поле -> описание).
    """
    repo = DescribeRepository()
    data = await asyncio.to_thread(repo.get_descriptions_formatted)
    return DescribeDTO(
        securities=data.get("securities") or {},
        marketdata=data.get("marketdata") or {},
    )


@router.get("/filter-options")
async def get_filter_options():
    """Получает доступные опции фильтров (уникальные значения для выпадающих списков).
    
    Загружает все облигации из кэша DataLoader и извлекает уникальные значения
    для полей LISTLEVEL, CURRENCYID (валюта) и BONDTYPE. Используется для заполнения
    выпадающих списков фильтров на фронтенде.
    
    Returns:
        Словарь с доступными опциями фильтров, содержащий:
        - listlevels: Отсортированный список уникальных уровней листинга
        - faceunits: Отсортированный список уникальных валют (например, ["SUR", "USD"])
        - bondtypes: Отсортированный список уникальных типов облигаций
            (например, ["exchange_bond", "ofz_bond", "corporate_bond"])
    """
    loader = get_data_loader()
    all_bonds = await loader.get_bonds()
    
    listlevels = list(set(b.LISTLEVEL for b in all_bonds if b.LISTLEVEL is not None))
    faceunits = list(set(b.CURRENCYID for b in all_bonds if b.CURRENCYID is not None))
    bondtypes = list(set(b.BONDTYPE for b in all_bonds if b.BONDTYPE is not None))
    
    return {
        "listlevels": sorted(listlevels),
        "faceunits": sorted(faceunits),
        "bondtypes": sorted(bondtypes),
    }
