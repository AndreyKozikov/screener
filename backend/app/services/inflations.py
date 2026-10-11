from typing import Optional

import httpx

from app.models.schemasDTO.inflations_dto import InflationDateFilter


class InflationService:

    def __init__(self):
        pass

    async def get_inflation_data(self, payload: InflationDateFilter):
        data = payload.model_dump(mode="json", exclude_none=True)
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/get_data_inflations",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                return result
        except Exception as e:
            raise

inflation_service: Optional[InflationService] = None

def get_inflation_service():
    global inflation_service

    if inflation_service is None:
        inflation_service = InflationService()

    return inflation_service