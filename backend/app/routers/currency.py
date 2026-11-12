"""Read-only API for currency rates already stored in the database."""

from datetime import date
from typing import Any, Dict, Optional

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.services.currency_service import get_currency_service

router = APIRouter(prefix="/api/currency", tags=["currency"])


@router.get("/rates")
async def get_currency_rates(
    target_date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to today"),
) -> Dict[str, Any]:
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD",
            ) from exc
    else:
        parsed_date = None
    return await asyncio.to_thread(get_currency_service().get_rates, parsed_date)
