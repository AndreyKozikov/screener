from fastapi import Query

from fastapi import APIRouter
import asyncio
from typing import List, Dict, Any

from db_repository.models.bonds_data_dto import BondsDataDTO
from db_repository.services.bond_service import get_bond_service
from db_repository.models.bonds_filters_dto import BondsListFiltersDTO
from db_repository.models.bond_response_dto import BondResponseDTO

bond_router = APIRouter(prefix="/api", tags=["bonds"])

@bond_router.post("/bonds", response_model=List[BondResponseDTO])  # Переработан
async def list_bonds(filters: BondsListFiltersDTO):
    service = get_bond_service()
    result = await service.get_bonds_list(data=filters)
    return result

@bond_router.get("/bond_counts")
async def bond_counts(exclude_spob: bool = Query(None)):
    service = get_bond_service()
    result = await service.bond_counts(exclude_spob=exclude_spob)
    return {"total": result}

@bond_router.get("/bonds/{secid}")
async def bond_details(secid: str):
    service = get_bond_service()
    result = await service.get_bond_details(secid)
    return result

@bond_router.post("/bonds_data_update")
async def bonds_data_update(payload: BondsDataDTO):
    service = get_bond_service()
    result = await service.bonds_data_update(data=payload)
    return result

@bond_router.get("/all_secids")
async def get_all_secids() -> List[str]:
    service = get_bond_service()
    result = await service.get_all_secids()
    return result
