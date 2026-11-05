"""Portfolio import and valuation endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.portfolio.dto import PortfolioValuationDTO, SavedPortfolioValuationRequestDTO
from app.portfolio.exceptions import PortfolioValuationError
from app.portfolio.service import PortfolioValuationService
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/api/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)

@router.post("/saved/{portfolio_id}/valuation", response_model=PortfolioValuationDTO)
async def saved_portfolio_valuation_endpoint(
    portfolio_id: int,
    payload: SavedPortfolioValuationRequestDTO,
    user: dict = Depends(get_current_user),
) -> PortfolioValuationDTO:
    """Load and value a saved portfolio entirely on the backend."""
    service = PortfolioValuationService()
    try:
        return await asyncio.to_thread(
            service.valuate_saved_portfolio,
            str(user["id"]),
            portfolio_id,
            payload.valuation_date,
        )
    except PortfolioValuationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("Saved portfolio valuation failed for %s", portfolio_id)
        raise HTTPException(
            status_code=500,
            detail="Не удалось выполнить оценку портфеля. Попробуйте позже.",
        ) from exc
