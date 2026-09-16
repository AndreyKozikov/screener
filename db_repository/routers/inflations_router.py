from db_repository.models.inflations import InflationExpectationsBase
from fastapi import APIRouter
from db_repository.services.inflation_service import get_inflation_service

inflation_router = APIRouter(prefix="/api", tags=["Inflations"])

@inflation_router.post("/inflation_expectations_update")
async def inflation_expectations_update(payload: list[InflationExpectationsBase]):
    service = get_inflation_service()
    print(payload)
    result = await service.inflation_expectations_update(data=payload)

    return result