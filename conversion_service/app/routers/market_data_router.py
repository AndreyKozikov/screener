"""HTTP API for refreshing and reading external market datasets."""

import asyncio
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from conversion_service.app.models.coupons_dto import (
    Coupon,
    CouponsBySecid,
    CouponsListResponse,
    MultipleCouponsResponse,
)
from conversion_service.app.models.rates_dto import RuoniaDataResponse
from conversion_service.app.services.bond_ratings_update_service import BondRatingsPipelineService
from conversion_service.app.services.coupon_service import get_coupon_service
from conversion_service.app.services.currency_update_service import get_currency_service
from conversion_service.app.services.keyrate_update_service import get_keyrate_service
from conversion_service.app.services.ruonia_update_service import get_ruonia_service
from conversion_service.app.services.trading_history_update_service import get_trading_history_service
from conversion_service.app.services.zerocupon_update_service import get_zerocupon_update_service

logger = logging.getLogger(__name__)

currency_router = APIRouter(prefix="/currency", tags=["currency"])
ruonia_router = APIRouter(prefix="/ruonia", tags=["ruonia"])
keyrate_router = APIRouter(prefix="/keyrate", tags=["keyrate"])
rating_router = APIRouter(prefix="/rating", tags=["rating"])
trading_history_router = APIRouter(prefix="/trading-history", tags=["trading-history"])
coupons_router = APIRouter(prefix="/bonds", tags=["coupons"])
zerocupon_router = APIRouter(prefix="/zerocupon", tags=["zerocupon"])

_ratings_service: Optional[BondRatingsPipelineService] = None


def _get_ratings_service() -> BondRatingsPipelineService:
    global _ratings_service
    if _ratings_service is None:
        _ratings_service = BondRatingsPipelineService()
    return _ratings_service


@currency_router.get("/rates")
async def get_currency_rates(
    target_date: Optional[str] = Query(None, description="Date to get rates for (YYYY-MM-DD), defaults to today"),
) -> Dict[str, Any]:
    try:
        parsed_date = date.fromisoformat(target_date) if target_date else None
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD",
        ) from exc
    try:
        return await asyncio.to_thread(get_currency_service().get_rates, parsed_date, False)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get currency rates: {exc}") from exc


@currency_router.post("/refresh")
async def refresh_currency_rates(
    target_date: Optional[str] = Query(None, description="Date to refresh rates for (YYYY-MM-DD), defaults to today"),
) -> Dict[str, Any]:
    try:
        parsed_date = date.fromisoformat(target_date) if target_date else None
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {target_date}. Expected format: YYYY-MM-DD",
        ) from exc
    return await asyncio.to_thread(get_currency_service().refresh_rates, parsed_date)


def _parse_iso_date(value: Optional[str], param_name: str) -> Optional[date]:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name} format. Use ISO date (YYYY-MM-DD).",
        ) from exc


@keyrate_router.post("/load")
async def load_keyrate_data() -> Dict[str, float]:
    try:
        return await asyncio.to_thread(get_keyrate_service().load_keyrate_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse key rate data: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load key rate data: {exc}") from exc


@keyrate_router.get("/data")
async def get_keyrate_data(
    from_: Optional[str] = Query(None, alias="from"),
    till: Optional[str] = Query(None),
) -> List[dict[str, Any]]:
    try:
        records = await asyncio.to_thread(
            get_keyrate_service().get_keyrate_list,
            _parse_iso_date(from_, "from"),
            _parse_iso_date(till, "till"),
        )
        return [row.model_dump(by_alias=True, mode="json") for row in records]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get key rate data: {exc}") from exc


@keyrate_router.get("/download/markdown")
async def download_keyrate_markdown(
    from_: Optional[str] = Query(None, alias="from"),
    till: Optional[str] = Query(None),
) -> Response:
    from_date = _parse_iso_date(from_, "from")
    till_date = _parse_iso_date(till, "till")
    records = await asyncio.to_thread(get_keyrate_service().get_keyrate_list, from_date, till_date)
    if not records:
        raise HTTPException(status_code=404, detail="No data found for the specified date range")
    columns = ["Дата", "Ключевая ставка, % годовых"]
    lines = ["# Ключевая ставка ЦБ", "", "| " + " | ".join(columns) + " |", "| --- | --- |"]
    for record in records:
        row = record.model_dump(by_alias=True, mode="json")
        values = [f"{row.get(column):.2f}" if isinstance(row.get(column), float) else str(row.get(column) or "") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    filename = f"keyrate_{from_ or 'all'}_{till or 'all'}.md"
    return Response(
        content="\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@ruonia_router.get("/data", response_model=RuoniaDataResponse, response_model_by_alias=True)
async def get_ruonia_data(
    date_from: Optional[str] = Query(None, description="Start date DD.MM.YYYY"),
    date_to: Optional[str] = Query(None, description="End date DD.MM.YYYY"),
) -> RuoniaDataResponse:
    try:
        return await asyncio.to_thread(
            get_ruonia_service().get_ruonia_data,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get RUONIA data: {exc}") from exc


@ruonia_router.get("/download/markdown")
async def download_ruonia_markdown(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    content = await asyncio.to_thread(get_ruonia_service().export_markdown, date_from, date_to)
    filename = "ruonia" + (f"_{date_from or ''}_{date_to or ''}" if date_from or date_to else "_all") + ".md"
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@ruonia_router.post("/refresh")
async def refresh_ruonia_data() -> Dict[str, Any]:
    return await asyncio.to_thread(get_ruonia_service().update_ruonia_data)


@rating_router.get("/{secid}")
async def get_bond_rating(secid: str, boardid: str = Query(...)) -> List[Dict[str, Any]]:
    try:
        ratings = _get_ratings_service().get_ratings_by_secid(secid)
        if not ratings:
            return [{
                "agency_id": 0, "agency_name_short_ru": "", "rating_level_id": 0,
                "rating_date": "", "rating_level_name_short_ru": "",
            }]
        from conversion_service.app.utils.rating_utils import standardize_rating

        _ = boardid
        return [{
            "agency_id": row.get("agency_id", 0),
            "agency_name_short_ru": row.get("agency_name_short_ru", ""),
            "rating_level_id": 0,
            "rating_date": row.get("rating_date", ""),
            "rating_level_name_short_ru": standardize_rating(row.get("rating_level_name")) or "",
        } for row in ratings]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get rating for {secid}: {exc}") from exc


@rating_router.post("/refresh")
async def refresh_ratings_data(force_update: bool = Query(False)) -> Dict[str, Any]:
    _ = force_update
    try:
        result = await asyncio.to_thread(_get_ratings_service().run_pipeline)
        return {"status": "ok", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refresh ratings: {exc}") from exc


@trading_history_router.get("/download")
async def download_trading_history() -> Dict[str, Any]:
    try:
        return await asyncio.to_thread(get_trading_history_service().download_history_all)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@coupons_router.post("/refresh-coupons")
async def refresh_coupons_data(
    force_refresh: bool = Query(False, description="Force refresh all coupons"),
) -> Dict[str, Any]:
    return await get_coupon_service().refresh_all(force_refresh)


@coupons_router.post("/{secid}/refresh-coupons", response_model=CouponsListResponse)
async def refresh_bond_coupons(
    secid: str,
    force_refresh: bool = Query(False),
) -> CouponsListResponse:
    try:
        data = await asyncio.to_thread(get_coupon_service().get_coupons, secid, force_refresh)
        return CouponsListResponse(coupons=[Coupon(**item) for item in data.get("coupons", [])])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refresh coupons for {secid}: {exc}") from exc


@coupons_router.get("/{secid}/coupons", response_model=CouponsListResponse)
async def get_bond_coupons(
    secid: str,
    secids: Optional[List[str]] = Query(None),
    force_refresh: bool = Query(False),
) -> CouponsListResponse:
    service = get_coupon_service()
    if secids:
        clean_secids = list(dict.fromkeys(item.strip() for item in secids if item and item.strip()))
        if not clean_secids:
            raise HTTPException(status_code=400, detail="At least one valid secid is required")
        target = secid if secid in clean_secids else clean_secids[0]
        batch = await asyncio.to_thread(service.get_coupons_batch, clean_secids, True)
        return CouponsListResponse(coupons=[Coupon(**item) for item in batch.get(target, {}).get("coupons", [])])
    try:
        data = await asyncio.to_thread(service.get_coupons, secid, force_refresh)
        return CouponsListResponse(coupons=[Coupon(**item) for item in data.get("coupons", [])])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get coupons: {exc}") from exc


@coupons_router.get("/coupons/batch", response_model=MultipleCouponsResponse)
async def get_bonds_coupons_batch(secids: List[str] = Query(..., min_length=1)) -> MultipleCouponsResponse:
    clean_secids = list(dict.fromkeys(item.strip() for item in secids if item and item.strip()))
    if not clean_secids:
        raise HTTPException(status_code=400, detail="At least one valid secid is required")
    batch = await asyncio.to_thread(get_coupon_service().get_coupons_batch, clean_secids, True)
    return MultipleCouponsResponse(data=[
        CouponsBySecid(
            secid=secid,
            coupons=[Coupon(**item) for item in batch.get(secid, {}).get("coupons", [])],
        )
        for secid in clean_secids
    ])


@zerocupon_router.post("/refresh")
async def refresh_zerocupon() -> Dict[str, Any]:
    try:
        result = await asyncio.to_thread(get_zerocupon_update_service().refresh)
        result["database_updated"] = True
        return result
    except Exception as exc:
        logger.exception("[API /zerocupon/refresh] ERROR: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error refreshing zerocupon data: {exc}") from exc


__all__ = [
    "coupons_router",
    "currency_router",
    "keyrate_router",
    "rating_router",
    "ruonia_router",
    "trading_history_router",
    "zerocupon_router",
]
