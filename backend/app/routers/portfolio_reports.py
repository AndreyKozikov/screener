"""Authenticated API for independently saved report-based portfolios."""

import logging
import asyncio
from datetime import date

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from decimal import Decimal
from typing import Annotated

from app.models.schemasDTO.portfolio_report_dto import (
    PortfolioReportImportResponse,
    PortfolioReportListItem,
)
from app.repository.db.remote_repository import PortfolioImportRepository, RemoteRepositoryError
from app.routers.auth import get_current_user
from config.settings import settings
from app.models import BondFilters
from app.portfolio.service import PortfolioValuationService
from app.portfolio.deals import PortfolioDealsService
from app.portfolio.dto import PortfolioDealsDTO
from app.portfolio.purchase_price import calculate_average_purchase_price
from app.services.bonds_service import get_bonds_list

router = APIRouter(prefix="/api/portfolios", tags=["imported portfolios"])
logger = logging.getLogger(__name__)
MAX_REPORT_SIZE = 10 * 1024 * 1024


@router.post("/import", response_model=PortfolioReportImportResponse, status_code=201)
async def import_portfolio_report_endpoint(
    file: UploadFile = File(..., description="HTML-отчёт брокера"),
    portfolio_name: str = Form(..., min_length=1, max_length=120),
    user: dict = Depends(get_current_user),
    authorization: Annotated[str | None, Header()] = None,
) -> PortfolioReportImportResponse:
    try:
        filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        content = await file.read(MAX_REPORT_SIZE + 1)
        if len(content) > MAX_REPORT_SIZE:
            raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "Размер отчёта не должен превышать 10 МБ."})

        conversion_url = f"{settings.CONVERSION_SERVICE_URL.rstrip('/')}/portfolios/import"
        headers = {"Authorization": authorization} if authorization else {}
        files = {"file": (filename, content, file.content_type or "application/octet-stream")}
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                conversion_url,
                data={"portfolio_name": portfolio_name},
                files=files,
                headers=headers,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("Conversion service returned a non-JSON response (%s)", response.status_code)
            raise HTTPException(status_code=502, detail={
                "code": "conversion_service_error", "message": "Сервис обработки отчётов вернул некорректный ответ.",
            }) from exc
        if response.is_error:
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
            raise HTTPException(status_code=response.status_code, detail=detail)
        return PortfolioReportImportResponse.model_validate(payload)
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.exception("Conversion service request failed")
        raise HTTPException(status_code=502, detail={
            "code": "conversion_service_unavailable", "message": "Сервис обработки отчётов недоступен. Попробуйте позже.",
        }) from exc
    finally:
        await file.close()


@router.get("", response_model=list[PortfolioReportListItem])
def list_imported_portfolios(user: dict = Depends(get_current_user)) -> list[PortfolioReportListItem]:
    try:
        rows = PortfolioImportRepository().list_for_user(str(user["id"]))
        return [PortfolioReportListItem.model_validate(row) for row in rows]
    except RemoteRepositoryError as exc:
        logger.exception("Could not load imported portfolios")
        raise HTTPException(status_code=502, detail={
            "code": "database_service_error", "message": "Не удалось загрузить список импортированных портфелей.",
        }) from exc


@router.get("/{portfolio_id}")
def get_imported_portfolio(portfolio_id: int, user: dict = Depends(get_current_user)) -> dict:
    try:
        report = PortfolioImportRepository().get_for_user(str(user["id"]), portfolio_id)
        if report is None:
            raise HTTPException(status_code=404, detail={
                "code": "portfolio_not_found", "message": "Импортированный портфель не найден.",
            })
        return report
    except HTTPException:
        raise
    except RemoteRepositoryError as exc:
        logger.exception("Could not load imported portfolio %s", portfolio_id)
        raise HTTPException(status_code=502, detail={
            "code": "database_service_error", "message": "Не удалось загрузить импортированный портфель.",
        }) from exc


@router.delete("/{portfolio_id}", status_code=204)
def delete_imported_portfolio(portfolio_id: int, user: dict = Depends(get_current_user)) -> Response:
    try:
        deleted = PortfolioImportRepository().delete_for_user(str(user["id"]), portfolio_id)
        if not deleted:
            raise HTTPException(status_code=404, detail={
                "code": "portfolio_not_found", "message": "Импортированный портфель не найден.",
            })
        return Response(status_code=204)
    except HTTPException:
        raise
    except RemoteRepositoryError as exc:
        logger.exception("Could not delete imported portfolio %s", portfolio_id)
        raise HTTPException(status_code=502, detail={
            "code": "database_service_error", "message": "Не удалось удалить импортированный портфель.",
        }) from exc


@router.get("/{portfolio_id}/table")
async def get_portfolio_table_rows(portfolio_id: int, user: dict = Depends(get_current_user)) -> list[dict]:
    """Prepare complete, read-only rows for the existing bonds table on the server."""
    try:
        portfolio = await asyncio.to_thread(
            PortfolioImportRepository().get_current_positions_for_user,
            str(user["id"]),
            portfolio_id,
        )
        if portfolio is None:
            raise HTTPException(status_code=404, detail={"code": "portfolio_not_found", "message": "Импортированный портфель не найден."})
        trades = await asyncio.to_thread(
            PortfolioImportRepository().get_current_position_trades_for_user,
            str(user["id"]),
            portfolio_id,
        )
        trades_by_security: dict[int, list[dict]] = {}
        for trade in trades:
            trades_by_security.setdefault(int(trade["security_id"]), []).append(trade)
        isin_set = list(dict.fromkeys(
            str(item["isin"]).strip().upper()
            for item in portfolio["positions"]
            if item.get("asset_type") == "bond" and item.get("isin")
        ))
        secid_set = list(dict.fromkeys(
            str(item["security_code"]).strip().upper()
            for item in portfolio["positions"]
            if item.get("asset_type") == "bond" and item.get("security_code")
        ))
        if not isin_set and not secid_set:
            return []
        market = await get_bonds_list(
            BondFilters(isins=isin_set or None, secids=secid_set or None),
            exclude_spob=False,
        )
        rows_by_isin = {
            str(bond.ISIN).strip().upper(): bond.model_dump(mode="json")
            for bond in market.bonds
            if bond.ISIN
        }
        rows_by_secid = {
            str(bond.SECID).strip().upper(): bond.model_dump(mode="json")
            for bond in market.bonds
            if bond.SECID
        }
        accrued_by_secid = await asyncio.to_thread(
            PortfolioValuationService().calculate_saved_portfolio_accrued_interest,
            str(user["id"]),
            portfolio_id,
            date.today(),
        )
        output = []
        for position in portfolio["positions"]:
            if position.get("asset_type") != "bond":
                continue
            security_isin = str(position.get("isin") or "").strip().upper()
            security_secid = str(position.get("security_code") or "").strip().upper()
            row = rows_by_secid.get(security_secid) if security_secid else None
            if row and security_isin and row.get("ISIN"):
                if str(row["ISIN"]).strip().upper() != security_isin:
                    row = None
            if row is None and security_isin:
                row = rows_by_isin.get(security_isin)
            if not row:
                continue
            quantity = int(position["quantity"])
            average_price = calculate_average_purchase_price(
                trades_by_security.get(int(position["security_id"]), []),
                quantity,
            )
            row["quantity"] = float(quantity)
            accrued = accrued_by_secid.get(str(row.get("SECID") or "").strip().upper())
            row["ACCRUEDINT"] = float(accrued) if accrued is not None else None
            row["averagePurchasePrice"] = float(average_price) if average_price is not None else None
            face = Decimal(str(row.get("FACEVALUE") or 0))
            coupon = Decimal(str(row.get("COUPONVALUE") or 0))
            period = row.get("COUPONPERIOD")
            frequency = round(365 / period) if period else None
            row["COUPON_FREQUENCY"] = frequency
            row["couponYieldToAveragePurchasePrice"] = (
                float(coupon * frequency * Decimal(10000) / (average_price * face))
                if frequency and face and average_price
                else None
            )
            row["DURATION_YEARS"] = float(row["DURATION"]) / 365 if row.get("DURATION") else None
            row["COUPON_YIELD_TO_PRICE"] = float(coupon * Decimal(10000) / (Decimal(str(row["PREVPRICE"])) * face) * frequency) if frequency and face and row.get("PREVPRICE") else None
            output.append(row)
        return output
    except HTTPException:
        raise
    except RemoteRepositoryError as exc:
        raise HTTPException(status_code=502, detail={"code": "database_service_error", "message": "Не удалось получить данные портфеля."}) from exc


@router.get("/{portfolio_id}/deals", response_model=PortfolioDealsDTO)
def get_portfolio_deals(
    portfolio_id: int,
    user: dict = Depends(get_current_user),
) -> PortfolioDealsDTO:
    """Вернуть сделки по облигациям текущего снимка выбранного портфеля."""
    try:
        result = PortfolioDealsService().get_current_portfolio_deals(
            str(user["id"]), portfolio_id
        )
        if result is None:
            raise HTTPException(status_code=404, detail={
                "code": "portfolio_not_found", "message": "Импортированный портфель не найден.",
            })
        return PortfolioDealsDTO.model_validate(result)
    except HTTPException:
        raise
    except RemoteRepositoryError as exc:
        logger.exception("Could not load portfolio deals for %s", portfolio_id)
        raise HTTPException(status_code=502, detail={
            "code": "database_service_error", "message": "Не удалось загрузить сделки портфеля.",
        }) from exc


__all__ = ["router"]
