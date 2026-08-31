from fastapi import APIRouter

from conversion_service.app.services.bonds_service import get_bonds_update_service



router = APIRouter(prefix="/update", tags=["update_bonds"])

@router.post("/bonds_data")
async def update_bonds():
    service = get_bonds_update_service()
    try:
        result = await service.update_bonds_data()
        return result
    except Exception as e:
        raise
