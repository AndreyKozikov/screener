import asyncio
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional

from app.services.currency_service import get_currency_service
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/currency", tags=["currency"])


@router.get("/rates")
async def get_currency_rates(
    target_date: Optional[str] = Query(None, description="Date to get rates for (YYYY-MM-DD), defaults to today")
) -> Dict[str, Any]:
    """
    Get currency exchange rates (EUR, USD, CNY) for the given date.
    
    Checks local cache first. If rates don't exist for the date,
    automatically fetches from CBR API and saves to file.
    
    Args:
        target_date: Date to get rates for in format YYYY-MM-DD (defaults to today)
        
    Returns:
        Dictionary with date and rates for EUR, USD, CNY
        
    Raises:
        HTTPException: If data cannot be loaded or fetched
    """
    logger = get_data_update_logger()
    logger.info(f"[API /currency/rates] Request received")
    
    try:
        # Parse date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
                logger.info(f"[API /currency/rates] Target date: {target_date}")
            except ValueError:
                logger.error(f"[API /currency/rates] ERROR: Invalid date format: {target_date}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD"
                )
        
        currency_service = get_currency_service()
        
        logger.info(f"[API /currency/rates] Getting currency rates (force_refresh=False - check cache first)...")
        rates_data = await asyncio.to_thread(
            currency_service.get_rates,
            parsed_date,
            False  # force_refresh=False - check cache first, auto-fetch if missing
        )
        
        logger.info(f"[API /currency/rates] Success: Rates retrieved for date {rates_data.get('date')}")
        logger.info(f"[API /currency/rates] Rates count: {len(rates_data.get('rates', {}))}")
        
        return rates_data
        
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.error(f"[API /currency/rates] ERROR: RuntimeError - {str(exc)}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /currency/rates] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get currency rates: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_currency_rates(
    target_date: Optional[str] = Query(None, description="Date to refresh rates for (YYYY-MM-DD), defaults to today")
) -> Dict[str, Any]:
    """
    Force refresh currency exchange rates from CBR API for the given date.
    
    Always fetches fresh data from CBR API, even if cached data exists.
    
    Args:
        target_date: Date to refresh rates for in format YYYY-MM-DD (defaults to today)
    
    Returns:
        Dictionary with refresh result
    """
    logger = get_data_update_logger()
    logger.info(f"[API /currency/refresh] Received request to refresh currency rates")
    
    try:
        # Parse date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
                logger.info(f"[API /currency/refresh] Target date: {target_date}")
            except ValueError:
                logger.error(f"[API /currency/refresh] ERROR: Invalid date format: {target_date}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD"
                )
        
        currency_service = get_currency_service()
        
        logger.info(f"[API /currency/refresh] Refreshing currency rates...")
        result = await asyncio.to_thread(
            currency_service.refresh_rates,
            parsed_date
        )
        
        logger.info(f"[API /currency/refresh] Refresh completed: {result}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /currency/refresh] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh currency rates: {str(exc)}"
        ) from exc

