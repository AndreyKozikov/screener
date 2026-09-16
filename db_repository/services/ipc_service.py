from typing import Optional
from db_repository.repository.ipc_repository import get_ipc_repository


class IpcService:

    def __init__(self):
        self._repository = get_ipc_repository()

    async def ipc_data_upodate(self, data):
        values = [record.model_dump() for record in data]
        result = self._repository.update_ipc_data(values)
        return result

    async def ipc_weekly_update(self, data):
        values = [record.model_dump() for record in data]
        result = self._repository.ipc_weekly_update(values)
        return result

ipc_service: Optional[IpcService] = None

def get_ipc_service():
    global ipc_service

    if ipc_service is None:
        ipc_service = IpcService()

    return ipc_service