"""Endpoints for updating e-disclosure indexes and document metadata."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from conversion_service.app.services.edisclosure_update_service import get_edisclosure_update_service

router = APIRouter(prefix="/edisclosure", tags=["edisclosure"])


@router.post("/fetch-emission-documents")
def fetch_emission_documents(
    limit: Optional[int] = Query(None, description="Количество эмитентов для обработки. По умолчанию — все."),
) -> Dict[str, Any]:
    try:
        return get_edisclosure_update_service().fetch_emission_documents(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка при скачивании эмиссионных документов: {exc}") from exc


@router.post("/populate-emitent-edisclosure")
def populate_emitent_edisclosure() -> Dict[str, int]:
    try:
        return get_edisclosure_update_service().populate_emitent_edisclosure()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
