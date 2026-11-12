import asyncio
from typing import Optional

from app.models.schemasDTO.inflations_dto import InflationDateFilter
from app.repository.db.client import get_db_repository_client


class InflationService:

    def __init__(self):
        pass

    async def _post(self, path: str, payload: dict):
        client = get_db_repository_client()
        response = await asyncio.to_thread(client.post, path, json=payload)
        response.raise_for_status()
        return response.json()

    async def get_inflation_data(self, payload: InflationDateFilter):
        data = payload.model_dump(mode="json", exclude_none=True)
        return await self._post("/api/get_data_inflations", data)

    async def get_sustainable_inflation_data(self, payload: InflationDateFilter):
        data = payload.model_dump(mode="json", exclude_none=True)
        return await self._post("/api/sustainable_inflation_data_get", data)


inflation_service: Optional[InflationService] = None


def get_inflation_service():
    global inflation_service

    if inflation_service is None:
        inflation_service = InflationService()

    return inflation_service
