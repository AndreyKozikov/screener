import asyncio
from fastapi import APIRouter, HTTPException
from typing import Optional

from app.models.emitent import EmitentInfo
from app.services.emitent_service import get_emitent_service
from app.services.data_loader import get_data_loader
from typing import Dict, Any

router = APIRouter(prefix="/api/emitent", tags=["emitent"])


@router.get("/{secid}", response_model=EmitentInfo)
async def get_emitent_by_secid(secid: str):
    """
    Get emitent information by SECID.
    
    First, gets ISIN from bonds data by SECID.
    Then, searches for emitent data in bonds_emitent.json by ISIN.
    If not found, fetches data from MOEX API and saves to bonds_emitent.json.
    
    Returns:
        EmitentInfo with fields: is_traded, emitent_title, emitent_inn, type
    """
    try:
        # Get emitent service
        emitent_service = get_emitent_service()
        
        # Get ISIN by SECID from bonds data
        isin = await emitent_service.get_isin_by_secid(secid)
        
        if isin is None:
            raise HTTPException(
                status_code=404,
                detail=f"ISIN not found for SECID: {secid}"
            )
        
        # Get or fetch emitent data (wrap in asyncio.to_thread for I/O operations)
        emitent_data = await asyncio.to_thread(
            emitent_service.get_or_fetch_emitent,
            secid,
            isin
        )
        
        if emitent_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Emitent data not found for ISIN: {isin} (SECID: {secid})"
            )
        
        # Extract only required fields from full MOEX response
        required_fields = emitent_service.extract_required_fields(emitent_data)
        return EmitentInfo(**required_fields)
    
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get emitent data for SECID {secid}: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_emitents_data() -> Dict[str, Any]:
    """
    Refresh emitent data for all bonds from bonds.json file.
    
    Reads SECID and ISIN from bonds.json and updates emitent data for each bond
    by fetching from MOEX API. All processing is done on the backend.
    
    Returns:
        Dictionary with refresh statistics: total, updated, errors, skipped
    """
    print(f"\n{'='*80}")
    print(f"[EMITENT REFRESH] Starting emitents refresh for all bonds")
    print(f"{'='*80}")
    
    try:
        emitent_service = get_emitent_service()
        data_loader = get_data_loader()
        
        # Get all bonds details
        print(f"[EMITENT REFRESH] Loading bonds data...")
        bonds_details = await data_loader.get_bond_details()
        bonds_count = len(bonds_details)
        print(f"[EMITENT REFRESH] Found {bonds_count} bonds to process")
        
        # Refresh all emitents (wrap in asyncio.to_thread for I/O operations)
        summary = await asyncio.to_thread(
            emitent_service.refresh_all_emitents,
            bonds_details
        )
        
        print(f"[EMITENT REFRESH] Refresh completed:")
        print(f"[EMITENT REFRESH]   Total bonds: {summary.get('total', 0)}")
        print(f"[EMITENT REFRESH]   Updated: {summary.get('updated', 0)}")
        print(f"[EMITENT REFRESH]   Errors: {summary.get('errors', 0)}")
        print(f"[EMITENT REFRESH]   Skipped: {summary.get('skipped', 0)}")
        print(f"{'='*80}\n")
        
        return {
            "status": "ok",
            **summary
        }
        
    except Exception as exc:
        error_type = type(exc).__name__
        print(f"[EMITENT REFRESH] ERROR: {error_type} - {str(exc)}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh emitents: {str(exc)}"
        ) from exc

