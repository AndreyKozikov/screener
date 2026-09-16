from unittest import result

from db_repository.models.ipc import IpcBase, IpcWeeklyBase
from fastapi import APIRouter
from db_repository.services.ipc_service import get_ipc_service

ipc_router = APIRouter(prefix="/api", tags=["IPC"])

@ipc_router.post("/ipc_update")
async def ipc_data_update(payload: list[IpcBase]):
    service = get_ipc_service()
    result = await service.ipc_data_upodate(data=payload)

    return result

@ipc_router.post("/ipc_weekly_update")
async def ipc_weekly_update(payload: list[IpcWeeklyBase]):
    service = get_ipc_service()
    result = await service.ipc_weekly_update(data=payload)
    return result