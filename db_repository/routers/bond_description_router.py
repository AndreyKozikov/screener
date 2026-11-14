"""API endpoint for persisting MOEX bond descriptions."""

from typing import Any

from fastapi import APIRouter

from db_repository.services.bond_description_service import get_bond_description_service


bond_description_router = APIRouter(prefix="/api/bond_descriptions", tags=["bond descriptions"])


@bond_description_router.post("/update")
async def update_bond_descriptions(descriptions: dict[str, dict[str, Any]]):
    return get_bond_description_service().update(descriptions)
