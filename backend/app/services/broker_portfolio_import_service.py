"""Parse broker holdings into the position values consumed by the frontend."""

from app.models.schemasDTO.broker_portfolio_dto import (
    BrokerPortfolioImportResponse,
    BrokerPortfolioPositionDTO,
)
from app.utils.broker_report_parser import parse_broker_report


async def import_broker_report(content: bytes) -> BrokerPortfolioImportResponse:
    parsed = parse_broker_report(content)

    return BrokerPortfolioImportResponse(
        imported_count=len(parsed.holdings),
        positions=[
            BrokerPortfolioPositionDTO(
                isin=holding.isin,
                quantity=holding.quantity,
                averagePurchasePrice=round(holding.average_purchase_price, 6),
            )
            for holding in parsed.holdings
        ],
        warnings=parsed.warnings,
    )
