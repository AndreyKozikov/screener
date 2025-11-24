import asyncio

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date

from app.models.bond import BondDetail
from app.models.filters import BondFilters
from app.models.responses import BondsListResponse
from app.models.coupons import BondCouponsResponse, CouponsListResponse
from app.services.data_loader import get_data_loader
from app.services.bond_filter import filter_bonds
from app.services.coupon_service import get_coupon_service
from app.config import settings

router = APIRouter(prefix="/api/bonds", tags=["bonds"])


@router.get("/", response_model=BondsListResponse)
async def list_bonds(
    coupon_min: Optional[float] = Query(None, ge=0, le=100),
    coupon_max: Optional[float] = Query(None, ge=0, le=100),
    matdate_from: Optional[date] = Query(None),
    matdate_to: Optional[date] = Query(None),
    listlevel: Optional[List[int]] = Query(None),
    faceunit: Optional[List[str]] = Query(None),
):
    """
    Get filtered list of bonds.
    Returns ALL filtered data - pagination and search are handled on client side.
    
    Supports filtering by:
    - Coupon rate range (coupon_min, coupon_max)
    - Maturity date range (matdate_from, matdate_to)
    - List level (listlevel)
    - Currency face unit (faceunit)
    
    Note: Search filtering is done on client side, not on server.
    """
    loader = get_data_loader()
    all_bonds = await loader.get_bonds()
    
    # Create filters for filtering (skip/limit not used - we return all data)
    filters = BondFilters(
        coupon_min=coupon_min,
        coupon_max=coupon_max,
        matdate_from=matdate_from,
        matdate_to=matdate_to,
        listlevel=listlevel,
        faceunit=faceunit,
        search=None,  # Search is handled on client side
        skip=0,
        limit=1000,  # Default value for model validation (NOT used - we return all)
    )
    
    # Debug: log filter parameters
    if listlevel:
        print(f"DEBUG: Filtering by listlevel: {listlevel}")
    if faceunit:
        print(f"DEBUG: Filtering by faceunit: {faceunit}")
    
    # Apply filters (this returns ALL filtered bonds, no pagination)
    filtered = filter_bonds(all_bonds, filters)
    total_filtered = len(filtered)
    
    # CRITICAL: Return ALL filtered data - NO pagination, NO limit, NO slicing
    # All bonds are returned for client-side pagination in AG Grid
    # We return the complete list without any slicing
    all_filtered_bonds = list(filtered)  # Make sure it's a complete list
    
    response_data = {
        "total": len(all_bonds),
        "filtered": total_filtered,
        "skip": 0,
        "limit": total_filtered,  # Actual number returned (not a limit!)
        "bonds": all_filtered_bonds,  # ALL filtered bonds - complete list
    }
    
    # Debug: verify we're returning all data
    print(f"DEBUG bonds endpoint: filtered={total_filtered}, returning={len(all_filtered_bonds)} bonds")
    
    return BondsListResponse(**response_data)

@router.post("/refresh")
async def refresh_bonds_data():
    """
    Download the latest bonds dataset from MOEX and refresh cached data.
    Also clears metadata cache (columns and descriptions) to ensure fresh data.
    """
    loader = get_data_loader()
    
    try:
        summary = await asyncio.to_thread(
            loader.refresh_bonds_dataset,
            settings.MOEX_BONDS_URL,
        )
        # Also clear metadata cache to ensure columns and descriptions are reloaded
        loader.clear_metadata_cache()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    
    return {
        "status": "ok",
        "updated": summary,
        "source": settings.MOEX_BONDS_URL,
        "metadata_cache_cleared": True,
    }


@router.get("/{secid}", response_model=BondDetail)
async def get_bond_detail(secid: str):
    """
    Get detailed information for a specific bond by SECID.
    
    Returns complete bond data including securities, marketdata, and yields.
    """
    loader = get_data_loader()
    details = await loader.get_bond_details()
    
    if secid not in details:
        raise HTTPException(status_code=404, detail=f"Bond {secid} not found")
    
    bond_data = details[secid]
    return BondDetail(**bond_data)


@router.get("/{secid}/coupons", response_model=CouponsListResponse)
async def get_bond_coupons(secid: str, force_refresh: bool = Query(False, description="Force refresh from MOEX API")):
    """
    Get coupon payments data for a specific bond by SECID.
    
    Returns list of coupons with coupondate, value (sum), and valueprc (rate).
    If data is missing or older than 14 days, automatically downloads from MOEX API.
    """
    try:
        coupon_service = get_coupon_service()
        coupons_data = await asyncio.to_thread(
            coupon_service.get_coupons_only,
            secid,
            force_refresh
        )
        
        # Convert dicts to Coupon models
        from app.models.coupons import Coupon
        coupons = [Coupon(**coupon) for coupon in coupons_data]
        
        return CouponsListResponse(coupons=coupons)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get coupons for {secid}: {str(exc)}") from exc
