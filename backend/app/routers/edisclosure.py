"""Роутеры для работы с e-disclosure.ru."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import LlmProviderUnavailableError
from app.services.edisclosure_service import get_edisclosure_service

router = APIRouter(prefix="/api/edisclosure", tags=["edisclosure"])


@router.post("/fetch-emission-documents")
async def fetch_emission_documents(
    limit: Optional[int] = Query(
        None,
        description="Количество эмитентов для обработки. По умолчанию — все.",
    ),
) -> Dict[str, Any]:
    """Скачивает эмиссионные документы эмитентов с e-disclosure.ru.

    Для каждого эмитента из emitent_edisclosure загружает HTML-страницу
    эмиссионных документов, парсит таблицу и сохраняет записи в БД.
    Приоритет: сначала эмитенты без документов в таблице.

    Args:
        limit: Количество эмитентов для обработки. None — все.

    Returns:
        JSON со статистикой: processed, total_docs_added, empty_count.
    """
    try:
        service = get_edisclosure_service()
        return service.fetch_emission_documents(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при скачивании эмиссионных документов: {exc}",
        ) from exc


@router.post("/populate-emitent-edisclosure")
async def populate_emitent_edisclosure_endpoint() -> Dict[str, int]:
    """Заполняет таблицу соответствия id эмитента (MOEX) и id на e-disclosure.ru.

    Для каждого эмитента с непустым ИНН из таблицы emitents выполняет поиск
    компании на e-disclosure.ru по ИНН и сохраняет edisclosure_id в таблицу
    emitent_edisclosure через репозиторий. Эмитенты, уже в таблице, пропускаются.

    Returns:
        Статистика: total_emitents, already_in_table, to_process, saved, skipped.
    """
    service = get_edisclosure_service()
    return service.populate_emitent_edisclosure()
