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
    yield_min: Optional[float] = Query(None, ge=0, le=100),
    yield_max: Optional[float] = Query(None, ge=0, le=100),
    coupon_yield_min: Optional[float] = Query(None, ge=0, le=100),
    coupon_yield_max: Optional[float] = Query(None, ge=0, le=100),
    matdate_from: Optional[date] = Query(None),
    matdate_to: Optional[date] = Query(None),
    listlevel: Optional[List[int]] = Query(None),
    faceunit: Optional[List[str]] = Query(None),
    bondtype: Optional[List[str]] = Query(None),
    coupon_type: Optional[List[str]] = Query(None),
    rating_min: Optional[str] = Query(None),
    rating_max: Optional[str] = Query(None),
):
    """
    Get filtered list of bonds.
    Returns ALL filtered data - pagination and search are handled on client side.
    
    Supports filtering by:
    - Coupon rate range (coupon_min, coupon_max)
    - Yield to maturity range (yield_min, yield_max)
    - Coupon yield to price range (coupon_yield_min, coupon_yield_max)
    - Maturity date range (matdate_from, matdate_to)
    - List level (listlevel)
    - Currency face unit (faceunit)
    - Bond type (bondtype)
    - Coupon type (coupon_type) - FIX or FLOAT
    - Rating range (rating_min, rating_max)
    
    Note: Search filtering is done on client side, not on server.
    """
    loader = get_data_loader()
    all_bonds = await loader.get_bonds()
    
    # Create filters for filtering (skip/limit not used - we return all data)
    filters = BondFilters(
        coupon_min=coupon_min,
        coupon_max=coupon_max,
        yield_min=yield_min,
        yield_max=yield_max,
        coupon_yield_min=coupon_yield_min,
        coupon_yield_max=coupon_yield_max,
        matdate_from=matdate_from,
        matdate_to=matdate_to,
        listlevel=listlevel,
        faceunit=faceunit,
        bondtype=bondtype,
        coupon_type=coupon_type,
        rating_min=rating_min,
        rating_max=rating_max,
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


@router.post("/refresh-coupons")
async def refresh_coupons_data():
    """
    Refresh coupons data for all bonds from bonds.json file.
    
    Reads SECID from bonds.json and updates coupon data for each bond
    by fetching from MOEX API. All processing is done on the backend.
    
    Returns:
        Dictionary with refresh statistics: total, updated, errors, skipped
    """
    print(f"\n{'='*80}")
    print(f"[COUPONS REFRESH] Starting coupons refresh for all bonds")
    print(f"{'='*80}")
    
    try:
        coupon_service = get_coupon_service()
        data_loader = get_data_loader()
        
        # Get all bonds data
        print(f"[COUPONS REFRESH] Loading bonds data...")
        bonds_list = await data_loader.get_bonds()
        bonds_count = len(bonds_list)
        print(f"[COUPONS REFRESH] Found {bonds_count} bonds to process")
        
        # Statistics
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        # Process each bond
        for idx, bond in enumerate(bonds_list):
            secid = bond.SECID
            
            if not secid:
                print(f"[COUPONS REFRESH] Bond {idx + 1}/{bonds_count}: Skipping - missing SECID")
                skipped_count += 1
                continue
            
            print(f"[COUPONS REFRESH] Processing bond {idx + 1}/{bonds_count}: SECID={secid}")
            
            try:
                # Get coupons with force_refresh=True to fetch from MOEX
                await asyncio.to_thread(
                    coupon_service.get_coupons,
                    secid,
                    True  # force_refresh=True - fetch from MOEX
                )
                updated_count += 1
                print(f"[COUPONS REFRESH] Successfully updated coupons for {secid}")
            except Exception as exc:
                error_type = type(exc).__name__
                print(f"[COUPONS REFRESH] ERROR: Failed to update coupons for {secid} - {error_type}: {str(exc)}")
                error_count += 1
                # Continue processing other bonds even if one fails
                continue
        
        summary = {
            "status": "ok",
            "total_bonds": bonds_count,
            "updated": updated_count,
            "errors": error_count,
            "skipped": skipped_count
        }
        
        print(f"[COUPONS REFRESH] Refresh completed:")
        print(f"[COUPONS REFRESH]   Total bonds: {bonds_count}")
        print(f"[COUPONS REFRESH]   Updated: {updated_count}")
        print(f"[COUPONS REFRESH]   Errors: {error_count}")
        print(f"[COUPONS REFRESH]   Skipped: {skipped_count}")
        print(f"{'='*80}\n")
        
        return summary
        
    except Exception as exc:
        error_type = type(exc).__name__
        print(f"[COUPONS REFRESH] ERROR: {error_type} - {str(exc)}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh coupons: {str(exc)}"
        ) from exc


@router.get("/{secid}/coupons", response_model=CouponsListResponse)
async def get_bond_coupons(secid: str, force_refresh: bool = Query(False, description="Force refresh from MOEX API")):
    """
    Get coupon payments data for a specific bond by SECID.
    
    Returns list of coupons with coupondate, value (sum), and valueprc (rate).
    If data is missing or older than 14 days, automatically downloads from MOEX API.
    """
    try:
        coupon_service = get_coupon_service()
        # Get full coupon data to access amortizations with coupon_type
        full_coupon_data = await asyncio.to_thread(
            coupon_service.get_coupons,
            secid,
            force_refresh
        )
        
        # Extract coupons and coupon_type
        coupons_data = full_coupon_data.get("coupons", [])
        amortizations = full_coupon_data.get("amortizations", [])
        
        # Get coupon_type from amortizations (all amortizations have the same coupon_type)
        coupon_type = None
        if amortizations and len(amortizations) > 0:
            coupon_type = amortizations[0].get("coupon_type")
        
        # Convert dicts to Coupon models
        from app.models.coupons import Coupon
        coupons = [Coupon(**coupon) for coupon in coupons_data]
        
        return CouponsListResponse(coupons=coupons, coupon_type=coupon_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get coupons for {secid}: {str(exc)}") from exc
