from typing import Optional
from db_repository.models.inflations import InflationExpectationsBase
from db_repository.repository.inflation_repository import get_inflation_repository

class InflationService:
    def __init__(self):
        self._repository = get_inflation_repository()

    async def inflation_expectations_update(self, data: list[InflationExpectationsBase]):
        values = [record.model_dump() for record in data]
        result = self._repository.inflation_expectations_update(values)
        return result


inflation_service: Optional[InflationService] = None

def get_inflation_service():
    global inflation_service

    if inflation_service is None:
        inflation_service = InflationService()

    return inflation_service