"""Schemas for creating and listing portfolios imported from broker reports."""

from pydantic import BaseModel, Field


class PortfolioReportImportResponse(BaseModel):
    portfolio_id: int
    portfolio_name: str
    report_period_start: str | None = None
    report_period_end: str | None = None
    import_status: str
    trade_count: int = 0
    security_count: int = 0
    cash_operation_count: int = 0
    income_payment_count: int = 0
    position_count: int = 0
    security_movement_count: int = 0
    parse_error_count: int = 0
    duplicate: bool = False
    warnings: list[str] = Field(default_factory=list)


class PortfolioReportListItem(BaseModel):
    portfolio_id: int
    portfolio_name: str
    base_currency: str
    source_file_name: str
    report_period_start: str | None = None
    report_period_end: str | None = None
    created_at: str
    import_status: str
    records_summary: dict[str, int] = Field(default_factory=dict)
