"""Broker report import API owned by the conversion service."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from conversion_service.app.portfolio_reports.auth import get_current_user
from conversion_service.app.portfolio_reports.parser import BrokerStatementParseError
from conversion_service.app.portfolio_reports.schemas import PortfolioReportImportResponse
from conversion_service.app.portfolio_reports.service import (
    DuplicatePortfolioReportError,
    import_statement_report,
)
from conversion_service.app.repository.db.remote_repository import (
    RemoteRepositoryError,
)


router = APIRouter(prefix="/portfolios", tags=["imported portfolios"])
logger = logging.getLogger(__name__)
MAX_REPORT_SIZE = 10 * 1024 * 1024


@router.post("/import", response_model=PortfolioReportImportResponse, status_code=201)
async def import_portfolio_report_endpoint(
    file: UploadFile = File(..., description="HTML-отчёт брокера"),
    portfolio_name: str = Form(..., min_length=1, max_length=120),
    user: dict = Depends(get_current_user),
) -> PortfolioReportImportResponse:
    try:
        filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix not in {"html", "htm"}:
            raise HTTPException(status_code=400, detail={"code": "unsupported_format", "message": "Загрузите HTML-отчёт (.html или .htm)."})
        normalized_name = portfolio_name.strip()
        if not normalized_name:
            raise HTTPException(status_code=422, detail={"code": "portfolio_name_required", "message": "Укажите название портфеля."})
        content = await file.read(MAX_REPORT_SIZE + 1)
        if len(content) > MAX_REPORT_SIZE:
            raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "Размер отчёта не должен превышать 10 МБ."})
        result = await import_statement_report(
            content=content,
            portfolio_name=normalized_name,
            source_file_name=filename,
            user_id=str(user["id"]),
        )
        return PortfolioReportImportResponse.model_validate(result)
    except HTTPException:
        raise
    except BrokerStatementParseError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_report", "message": str(exc)}) from exc
    except DuplicatePortfolioReportError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_report", "message": str(exc), "portfolio_id": exc.portfolio_id,
        }) from exc
    except RemoteRepositoryError as exc:
        logger.exception("Portfolio report database service failed")
        raise HTTPException(status_code=502, detail={
            "code": "database_service_error", "message": "Микросервис БД не сохранил портфель. Попробуйте позже.",
        }) from exc
    except Exception as exc:
        logger.exception("Portfolio report import failed")
        raise HTTPException(status_code=502, detail={
            "code": "import_failed", "message": "Не удалось сохранить отчёт брокера.",
        }) from exc
    finally:
        await file.close()


__all__ = ["router"]
