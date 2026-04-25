import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.repository.db.event_detail_repository import EventDetailRepository
from app.services.event_processing_service import EventProcessingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post("/process-events", response_model=Dict[str, Any])
def process_events(
    inn: Optional[str] = Query(None, description="ИНН эмитента для фильтрации обработки файлов. Если не указан - анализируются все файлы.")
):
    """
    Запускает пайплайн обработки событий: чтение JSON файлов, 
    извлечение атрибутов через LLM и сохранение в БД.
    """
    logger.info("Получен запрос POST /pipeline/process-events (INN: %s)", inn)
    repository = EventDetailRepository()
    service = EventProcessingService(repository)
    stats = service.process_all_events(target_inn=inn)
    logger.info("Обработка завершена. Статистика: %s", stats)
    return stats
