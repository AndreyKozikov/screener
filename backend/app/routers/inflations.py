from app.models.schemasDTO.inflations_dto import InflationDateFilter
from fastapi import APIRouter
from app.services.inflations import get_inflation_service


inflation_router = APIRouter(prefix="/api/inflations", tags=["Inflations"])

@inflation_router.post("/get_data")
async def get_inflation_data(payload: InflationDateFilter):
    service = get_inflation_service()
    print(payload)
    result = await service.get_inflation_data(payload)
    return result