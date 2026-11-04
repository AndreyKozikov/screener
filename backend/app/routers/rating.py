"""Read-only API for stored bond ratings."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.repository.db.bond_ratings_repository import BondRatingsRepository
from app.utils.rating_utils import standardize_rating

router = APIRouter(prefix="/api/rating", tags=["rating"])


def _format_rating_for_api(rating: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "agency_id": rating.get("agency_id", 0),
        "agency_name_short_ru": rating.get("agency_name_short_ru", ""),
        "rating_level_id": 0,
        "rating_date": rating.get("rating_date", ""),
        "rating_level_name_short_ru": standardize_rating(rating.get("rating_level_name")) or "",
    }


@router.get("/{secid}")
async def get_bond_rating(
    secid: str,
    boardid: str = Query(..., description="Board ID (e.g., TQCB, TQOB)"),
) -> List[Dict[str, Any]]:
    _ = boardid
    try:
        ratings = BondRatingsRepository().get_ratings_by_secid(secid)
        if not ratings:
            return [{
                "agency_id": 0,
                "agency_name_short_ru": "",
                "rating_level_id": 0,
                "rating_date": "",
                "rating_level_name_short_ru": "",
            }]
        return [_format_rating_for_api(rating) for rating in ratings]
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rating for {secid}: {exc}",
        ) from exc
