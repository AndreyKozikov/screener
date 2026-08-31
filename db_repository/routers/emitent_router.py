from typing import Any
from db_repository.services.emitent_service import get_emitent_service

from fastapi import APIRouter

emitent_router = APIRouter(prefix="/api/emitents", tags=["emitents"])

@emitent_router.post("/update")
async def emitents_data_update(emitents_data: dict[str, Any]):
    service = get_emitent_service()
    result = await service.emitents_data_update(emitents_data)
    return result