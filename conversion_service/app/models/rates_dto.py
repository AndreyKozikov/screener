"""DTOs for monetary rates exposed by the conversion service."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KeyrateDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    dt: date = Field(alias="Дата")
    rate: float = Field(alias="Ключевая ставка, % годовых")


class RuoniaDTO(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        from_attributes=True,
    )

    date_stavki: str = Field(alias="Дата ставки")
    stavka_ruonia: Optional[float] = Field(None, alias="Ставка RUONIA, % годовых")
    volume_ruonia: Optional[float] = Field(None, alias="Объем сделок RUONIA, млрд руб.")
    count_deals: Optional[float] = Field(None, alias="Количество сделок, ед.")
    min_rate: Optional[float] = Field(None, alias="Минимальная процентная ставка, % годовых")
    percentile_25: Optional[float] = Field(None, alias="25-й процентиль по процентным ставкам, % годовых")
    percentile_75: Optional[float] = Field(None, alias="75-й процентиль по процентным ставкам, % годовых")
    max_rate: Optional[float] = Field(None, alias="Максимальная процентная ставка, % годовых")


class RuoniaDataResponse(BaseModel):
    data: List[RuoniaDTO]
    count: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
