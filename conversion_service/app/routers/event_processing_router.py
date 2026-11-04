"""Endpoints for processing downloaded issuer events into structured records."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from conversion_service.app.repository.db.remote_repository import EventDetailRepository
from conversion_service.app.services.event_processing_service import EventProcessingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/process-events", response_model=Dict[str, Any])
def process_events(
    inn: Optional[str] = Query(None, description="ИНН эмитента для фильтрации обработки файлов."),
) -> Dict[str, Any]:
    try:
        service = EventProcessingService(EventDetailRepository())
        return service.process_all_events(target_inn=inn)
    except Exception as exc:
        logger.exception("Event processing failed")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки событий: {exc}") from exc
