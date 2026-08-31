from fastapi import APIRouter
from typing import List
from fastapi import Body
from db_repository.services.ratings_service import get_ratings_service

ratings_router = APIRouter(prefix="/api/ratings", tags=["ratings"])

@ratings_router.post("/bonds", tags=["ratings"])
async def get_bond_ratings(bondids: List[int] = Body(...)):
    service = get_ratings_service()
    results = await service.get_bond_ratings(bondids)
    return results

@ratings_router.post("/emitents", tags=["ratings"])
async def get_bond_ratings(emitent_ids: List[int] = Body(...)):
    service = get_ratings_service()
    results = await service.get_emitent_ratings(emitent_ids)
    return results

@ratings_router.get("/bonds_rating_map", tags=["ratings"])
async def get_bond_ratings_map():
    service = get_ratings_service()
    results = await service.get_bonds_rating_map()
    return results

@ratings_router.get("/emitents_rating_map", tags=["ratings"])
async def get_bond_ratings_map():
    service = get_ratings_service()
    results = await service.get_emitents_rating_map()
    return results
