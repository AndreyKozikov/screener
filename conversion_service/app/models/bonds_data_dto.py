from typing import Any

from pydantic import BaseModel, RootModel

class BondDataDTO(BaseModel):
    securities: dict[str, Any]
    marketdata: dict[str, Any]
    marketdata_yields: dict[str, Any] = {}

class BondsDataDTO(RootModel[dict[str, BondDataDTO]]):
    pass