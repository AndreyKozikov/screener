"""Independent service for parsing and persisting full broker statements."""

from __future__ import annotations

import hashlib
from typing import Any

from app.repository.db.remote_repository import PortfolioImportRepository
from app.utils.broker_statement_parser import parse_broker_statement


class DuplicatePortfolioReportError(ValueError):
    def __init__(self, portfolio_id: int, portfolio_name: str) -> None:
        self.portfolio_id = portfolio_id
        self.portfolio_name = portfolio_name
        super().__init__("Этот файл уже импортирован в портфель «%s»." % portfolio_name)


async def import_statement_report(
    *, content: bytes, portfolio_name: str, source_file_name: str, user_id: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(content).hexdigest()
    repository = PortfolioImportRepository()
    existing = repository.find_duplicate(user_id=user_id, source_file_sha256=digest)
    if existing:
        raise DuplicatePortfolioReportError(existing["portfolio_id"], existing["portfolio_name"])
    parsed = parse_broker_statement(content)
    saved = repository.save_report_import(
        user_id=user_id,
        portfolio_name=portfolio_name,
        source_file_name=source_file_name,
        source_file_sha256=digest,
        report=parsed,
    )
    if saved.get("duplicate"):
        raise DuplicatePortfolioReportError(saved["portfolio_id"], saved["portfolio_name"])
    summary = saved.get("records_summary", {})
    return {
        **saved,
        "trade_count": summary.get("trades", 0),
        "security_count": summary.get("securities", 0),
        "cash_operation_count": summary.get("cash_operations", 0),
        "income_payment_count": summary.get("income_payments", 0),
        "position_count": summary.get("positions", 0),
        "security_movement_count": summary.get("security_movements", 0),
        "parse_error_count": summary.get("parse_errors", 0),
        "warnings": parsed.get("warnings", [])[:100],
    }


__all__ = ["DuplicatePortfolioReportError", "import_statement_report"]
