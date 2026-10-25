import asyncio
from typing import Any, Optional

import httpx

from app.utils.ipc_calculations import calculate_ipc_kpis


class IpcService:
    async def get_data(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=600) as client:
            monthly_response, weekly_response = await _fetch_ipc_data(client)
            monthly_response.raise_for_status()
            weekly_response.raise_for_status()
            monthly_data = monthly_response.json() or []
            weekly_data = weekly_response.json() or []

        return {
            "monthly": monthly_data,
            "weekly": weekly_data,
            "kpi": calculate_ipc_kpis(monthly_data, weekly_data),
        }


async def _fetch_ipc_data(client: httpx.AsyncClient) -> tuple[httpx.Response, httpx.Response]:
    monthly_response, weekly_response = await asyncio.gather(
        client.post("http://127.0.0.1:8964/api/ipc_monthly_get", json={}),
        client.post("http://127.0.0.1:8964/api/ipc_weekly_get", json={}),
    )
    return monthly_response, weekly_response


ipc_service: Optional[IpcService] = None


def get_ipc_service() -> IpcService:
    global ipc_service
    if ipc_service is None:
        ipc_service = IpcService()
    return ipc_service
