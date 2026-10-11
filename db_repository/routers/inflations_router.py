from db_repository.models.inflations import InflationExpectationsBase, InflationDataBase
from db_repository.models.inflations_dto import InflationDateFilter
from fastapi import APIRouter
from db_repository.services.inflation_service import get_inflation_service

inflation_router = APIRouter(prefix="/api", tags=["Inflations"])

@inflation_router.post("/inflation_expectations_update")
async def inflation_expectations_update(payload: list[InflationExpectationsBase]):
    service = get_inflation_service()
    result = await service.inflation_expectations_update(data=payload)

    return result

@inflation_router.post("/inflation_data_update")
async def update_inflation_data(payload: list[InflationDataBase]):
    service = get_inflation_service()
    result = await service.update_inflation_data(data=payload)

@inflation_router.post("/get_data_inflations")
async def get_inflation_values(payload: InflationDateFilter):
    service = get_inflation_service()
    result = await service.select_inflation_data(payload)
    return result

