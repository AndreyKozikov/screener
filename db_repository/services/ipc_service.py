from typing import Optional
from db_repository.repository.ipc_repository import get_ipc_repository
from db_repository.models.ipc import IpcBase
from db_repository.models.ipc_dto import IpcDateFilter, IpcWeeklyDTO


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

    async def ipc_weekly_select(
            self,
            data: IpcDateFilter,
    ) -> list[IpcWeeklyDTO]:
        values = data.model_dump()
        result = self._repository.ipc_weekly_data_select(data=values)
        return [
            IpcWeeklyDTO(
                start_date=row.start_date,
                end_date=row.end_date,
                ipc_weekly=row.ipc_weekly
            )
            for row in result
        ]

    async def ipc_monthly_select(
            self,
            data: IpcDateFilter,
    ) -> list[IpcBase]:
        values = data.model_dump()
        result = self._repository.ipc_monthly_data_select(data=values)
        return result


ipc_service: Optional[IpcService] = None

def get_ipc_service():
    global ipc_service

    if ipc_service is None:
        ipc_service = IpcService()

    return ipc_service