from fastapi import APIRouter
from typing import Dict, List

from app.services.data_loader import get_data_loader
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api", tags=["metadata"])


@router.get("/columns", response_model=Dict[str, str])
async def get_columns():
    """
    Get column name mappings (English field names to Russian display names).
    
    Returns dictionary like {"SECID": "Код инструмента", ...}
    """
    loader = get_data_loader()
    return await loader.get_column_mapping()


@router.get("/descriptions")
async def get_descriptions():
    """
    Get field descriptions.
    
    Returns detailed descriptions for each field.
    """
    loader = get_data_loader()
    return await loader.get_descriptions()


@router.get("/filter-options")
async def get_filter_options():
    """
    Get available filter options (distinct values for dropdowns).
    
    Returns:
    - Available list levels
    - Available currency face units
    - Available bond types
    """
    loader = get_data_loader()
    all_bonds = await loader.get_bonds()
    
    listlevels = list(set(b.LISTLEVEL for b in all_bonds if b.LISTLEVEL is not None))
    faceunits = list(set(b.FACEUNIT for b in all_bonds if b.FACEUNIT is not None))
    bondtypes = list(set(b.BONDTYPE for b in all_bonds if b.BONDTYPE is not None))
    
    return {
        "listlevels": sorted(listlevels),
        "faceunits": sorted(faceunits),
        "bondtypes": sorted(bondtypes),
    }


@router.post("/refresh-metadata")
async def refresh_metadata():
    """
    Clear metadata cache (columns and descriptions) to force reload from files.
    Useful when columns.json or describe.json files are updated.
    """
    logger = get_data_update_logger()
    logger.info("[API /refresh-metadata] Received request to refresh metadata cache")
    
    loader = get_data_loader()
    loader.clear_metadata_cache()
    
    logger.info("[API /refresh-metadata] Metadata cache cleared successfully")
    return {
        "status": "ok",
        "message": "Metadata cache cleared. Columns and descriptions will be reloaded on next request.",
    }