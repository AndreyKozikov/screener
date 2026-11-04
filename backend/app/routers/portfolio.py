"""Portfolio import and valuation endpoints."""

import asyncio
import logging
from pathlib import PurePath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.models.schemasDTO.broker_portfolio_dto import BrokerPortfolioImportResponse
from app.portfolio.dto import PortfolioValuationDTO, PortfolioValuationRequestDTO
from app.portfolio.exceptions import PortfolioValuationError
from app.portfolio.service import PortfolioValuationService
from app.routers.auth import get_current_user
from app.services.broker_portfolio_import_service import import_broker_report
from app.utils.broker_report_parser import BrokerReportParseError

router = APIRouter(
    prefix="/api/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)

MAX_REPORT_SIZE = 10 * 1024 * 1024


@router.post("/import/broker-report", response_model=BrokerPortfolioImportResponse)
async def import_broker_report_endpoint(
    file: UploadFile = File(..., description="HTML-отчёт брокера"),
) -> BrokerPortfolioImportResponse:
    """Parse end-of-period position values; bond data is loaded by the frontend."""
    suffix = PurePath(file.filename or "").suffix.lower()
    if suffix not in {".html", ".htm"}:
        raise HTTPException(status_code=400, detail="Загрузите HTML-отчёт брокера (.html или .htm).")

    content = await file.read(MAX_REPORT_SIZE + 1)
    if len(content) > MAX_REPORT_SIZE:
        raise HTTPException(status_code=413, detail="Размер отчёта не должен превышать 10 МБ.")

    try:
        return await import_broker_report(content)
    except BrokerReportParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Broker portfolio report import failed")
        raise HTTPException(
            status_code=502,
            detail="Не удалось обработать отчёт брокера. Попробуйте позже.",
        ) from exc
    finally:
        await file.close()


@router.post("/valuation", response_model=PortfolioValuationDTO)
async def portfolio_valuation_endpoint(
    payload: PortfolioValuationRequestDTO,
) -> PortfolioValuationDTO:
    """Оценивает портфель, состав которого передан с фронтенда.

    Расчёты выполняются в отдельном потоке, чтобы не блокировать event loop
    синхронными запросами к микросервису БД.
    """
    service = PortfolioValuationService()
    try:
        return await asyncio.to_thread(service.valuate, payload)
    except PortfolioValuationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("Portfolio valuation failed")
        raise HTTPException(
            status_code=500,
            detail="Не удалось выполнить оценку портфеля. Попробуйте позже.",
        ) from exc
