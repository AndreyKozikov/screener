from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from app.services.edisclosure_events_service import get_edisclosure_events_service

router = APIRouter(prefix="/edisclosure", tags=["edisclosure"])

@router.post("/emitent-events/fetch")
async def fetch_emitent_events_by_inn(
    inn: Optional[str] = Query(
        None,
        description="ИНН эмитента (10 или 12 цифр). Не указывать или пустая строка — "
        "выгрузка для всех эмитентов с непустым ИНН из таблицы emitents (пакетный режим).",
    ),
) -> Dict[str, Any]:
    """Все события эмитента с e-disclosure.ru по годам (без фильтра по заголовку) в JSON.

    Определяет начальный год по вкладкам на странице компании, затем для каждого года
    до текущего загружает события и полный текст, сохраняет в ``app/data/events/{inn}.json``.

    Если параметр ``inn`` отсутствует или пустой — для каждого уникального ИНН из БД
    (таблица emitents) выполняется тот же пайплайн; ответ — сводка пакета (results/errors).
    """
    try:
        service = get_edisclosure_events_service()
        if inn is None or inn.strip() == "":
            return service.fetch_and_save_emitent_events_for_all_emitents()
        return service.fetch_and_save_emitent_events_by_inn(inn.strip())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при выгрузке событий эмитента: {exc}",
        ) from exc
