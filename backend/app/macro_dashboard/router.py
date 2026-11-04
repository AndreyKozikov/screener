"""HTTP endpoint for the request-time macroeconomic dashboard."""

import logging

from fastapi import APIRouter, HTTPException

from app.macro_dashboard.builder import DashboardDataBuilder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/macro-dashboard", tags=["macro-dashboard"])
_builder = DashboardDataBuilder()


@router.get("")
async def get_macro_dashboard() -> dict:
    try:
        return await _builder.build()
    except Exception as exc:
        logger.exception("Failed to build the macroeconomic dashboard")
        raise HTTPException(status_code=500, detail="Не удалось сформировать макроэкономический дашборд") from exc
