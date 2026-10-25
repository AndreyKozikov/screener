from fastapi import APIRouter

from app.services.ipc_service import get_ipc_service


ipc_router = APIRouter(prefix="/api/ipc", tags=["IPC"])


@ipc_router.get("/data")
async def get_ipc_data():
    return await get_ipc_service().get_data()
