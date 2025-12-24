import asyncio
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from app.services.rating_service import get_rating_service
from app.services.data_loader import get_data_loader

router = APIRouter(prefix="/api/rating", tags=["rating"])


@router.get("/{secid}")
async def get_bond_rating(
    secid: str,
    boardid: str = Query(..., description="Board ID (e.g., TQCB, TQOB)")
) -> List[Dict[str, Any]]:
    """
    Get bond rating data by SECID and BOARDID from local cache only.
    
    Only reads from local file bonds_rating.json. Does NOT fetch from MOEX website.
    If data is not found in cache, returns empty rating list.
    Use POST /api/rating/refresh to update ratings from MOEX.
    
    Args:
        secid: Security ID
        boardid: Board ID
        
    Returns:
        List of rating dictionaries with keys: agency_id, agency_name_short_ru,
        rating_level_id, rating_date, rating_level_name_short_ru
        
    Raises:
        HTTPException: If data cannot be loaded from cache
    """
    print(f"\n{'='*80}")
    print(f"[RATING] Request received")
    print(f"{'='*80}")
    print(f"[RATING] SECID: {secid}")
    print(f"[RATING] BOARDID: {boardid}")
    
    try:
        rating_service = get_rating_service()
        
        print(f"[RATING] Calling rating service (force_refresh=False - only from cache)...")
        ratings_list = await asyncio.to_thread(
            rating_service.get_rating,
            secid,
            boardid,
            False  # force_refresh=False - only return cached data, no network requests
        )
        
        # Log response details
        if ratings_list and isinstance(ratings_list, list):
            ratings_count = len(ratings_list)
            print(f"[RATING] Success: Found {ratings_count} rating entries")
            if ratings_count > 0:
                first_rating = ratings_list[0]
                print(f"[RATING] First rating entry keys: {list(first_rating.keys()) if isinstance(first_rating, dict) else 'N/A'}")
                print(f"[RATING] Sample rating: {first_rating}")
        else:
            print(f"[RATING] Warning: Response is not a list or is empty")
            print(f"[RATING] Response type: {type(ratings_list)}")
        
        print(f"[RATING] Request completed successfully")
        print(f"{'='*80}\n")
        
        return ratings_list
    except RuntimeError as exc:
        print(f"[RATING] ERROR: RuntimeError - {str(exc)}")
        print(f"[RATING] Status: 502 Bad Gateway")
        print(f"{'='*80}\n")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        print(f"[RATING] ERROR: {error_type} - {str(exc)}")
        print(f"[RATING] Status: 500 Internal Server Error")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rating for {secid}: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_ratings_data(
    force_update: bool = Query(False, description="Force update all ratings regardless of last_updated date")
):
    """
    Refresh ratings for all bonds from bonds.json file.
    
    Reads SECID and BOARDID from bonds.json and updates ratings for each bond.
    All processing is done on the backend.
    
    Args:
        force_update: If True, update all ratings regardless of last_updated date.
                     If False, only update ratings that are missing or stale (>30 days).
    
    Returns:
        Dictionary with refresh statistics
    """
    print(f"\n{'='*80}")
    print(f"[RATING REFRESH] Starting ratings refresh for all bonds")
    print(f"[RATING REFRESH] Force update: {force_update}")
    print(f"{'='*80}")
    
    try:
        rating_service = get_rating_service()
        data_loader = get_data_loader()
        
        # Get all bonds data
        print(f"[RATING REFRESH] Loading bonds data...")
        bonds_list = await data_loader.get_bonds()
        bonds_count = len(bonds_list)
        print(f"[RATING REFRESH] Found {bonds_count} bonds to process")
        
        # Statistics
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        # Process each bond
        for idx, bond in enumerate(bonds_list):
            secid = bond.SECID
            boardid = bond.BOARDID
            
            if not secid or not boardid:
                print(f"[RATING REFRESH] Bond {idx + 1}/{bonds_count}: Skipping - missing SECID or BOARDID")
                skipped_count += 1
                continue
            
            print(f"[RATING REFRESH] Processing bond {idx + 1}/{bonds_count}: SECID={secid}, BOARDID={boardid}")
            
            try:
                # Get rating with force_refresh based on force_update parameter
                # If force_update=True, always fetch from MOEX regardless of date
                # If force_update=False, only fetch if missing or stale
                await asyncio.to_thread(
                    rating_service.get_rating,
                    secid,
                    boardid,
                    True,  # force_refresh=True - fetch from MOEX
                    force_update  # force_update_all - ignore date check if True
                )
                updated_count += 1
                print(f"[RATING REFRESH] Successfully updated rating for {secid}")
            except Exception as exc:
                error_type = type(exc).__name__
                print(f"[RATING REFRESH] ERROR: Failed to update rating for {secid} - {error_type}: {str(exc)}")
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
        
        print(f"[RATING REFRESH] Refresh completed:")
        print(f"[RATING REFRESH]   Total bonds: {bonds_count}")
        print(f"[RATING REFRESH]   Updated: {updated_count}")
        print(f"[RATING REFRESH]   Errors: {error_count}")
        print(f"[RATING REFRESH]   Skipped: {skipped_count}")
        print(f"{'='*80}\n")
        
        return summary
        
    except Exception as exc:
        error_type = type(exc).__name__
        print(f"[RATING REFRESH] ERROR: {error_type} - {str(exc)}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh ratings: {str(exc)}"
        ) from exc

