from typing import Optional

from fastapi import APIRouter
from conversion_service.app.services.emitents_service import get_emitent_service


router = APIRouter(prefix="/emitents", tags=["emitents"])


@router.post("/update")
async def update_emitents_data(secids: Optional[list[str]] = None):
    service = get_emitent_service()
    result = await service.update_emitents_data(secids)
    return result