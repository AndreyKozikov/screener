"""Request and response models for importing broker statements into a portfolio."""

from typing import List

from pydantic import BaseModel, Field

class BrokerPortfolioPositionDTO(BaseModel):
    """Position values derived from the broker report, keyed by ISIN."""

    isin: str
    quantity: int
    averagePurchasePrice: float


class BrokerPortfolioImportResponse(BaseModel):
    """Parsed positions ready to apply to the browser portfolio store."""

    imported_count: int
    positions: List[BrokerPortfolioPositionDTO]
    warnings: List[str] = Field(default_factory=list)

