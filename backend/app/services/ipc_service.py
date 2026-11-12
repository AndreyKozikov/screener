import asyncio
from typing import Any, Optional

from app.repository.db.client import get_db_repository_client
from app.utils.ipc_calculations import calculate_ipc_kpis


class IpcService:
    async def get_data(self) -> dict[str, Any]:
        client = get_db_repository_client()
        monthly_response, weekly_response = await asyncio.gather(
            asyncio.to_thread(client.post, "/api/ipc_monthly_get", json={}),
            asyncio.to_thread(client.post, "/api/ipc_weekly_get", json={}),
        )
        monthly_response.raise_for_status()
        weekly_response.raise_for_status()
        monthly_data = monthly_response.json() or []
        weekly_data = weekly_response.json() or []

        return {
            "monthly": monthly_data,
            "weekly": weekly_data,
            "kpi": calculate_ipc_kpis(monthly_data, weekly_data),
        }


ipc_service: Optional[IpcService] = None


def get_ipc_service() -> IpcService:
    global ipc_service
    if ipc_service is None:
        ipc_service = IpcService()
    return ipc_service
