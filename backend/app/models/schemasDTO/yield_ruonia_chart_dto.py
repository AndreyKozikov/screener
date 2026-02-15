"""DTO для ответа API графика сравнения доходности облигации и ставки RUONIA.

Нормализованные данные по датам: только дни, присутствующие в обеих таблицах
(история торгов по облигации и ставки RUONIA).
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BondYieldRuoniaChartItem(BaseModel):
    """Одна точка графика: дата, ставка RUONIA и доходность к погашению облигации.

    Attributes:
        date: Дата в формате YYYY-MM-DD.
        ruonia_rate: Ставка RUONIA, % годовых.
        yieldatwap: Доходность к погашению (yield at WAP), %.
    """

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    date: str = Field(description="Дата (YYYY-MM-DD)")
    ruonia_rate: Optional[float] = Field(None, description="Ставка RUONIA, % годовых")
    yieldatwap: Optional[float] = Field(None, description="Доходность к погашению (yieldatwap), %")


class BondYieldRuoniaChartResponse(BaseModel):
    """Ответ API с нормализованными данными для графика доходность облигации vs RUONIA.

    Attributes:
        secid: Идентификатор облигации (SECID).
        data: Список точек графика (только даты, присутствующие в обеих источниках).
    """

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    secid: str = Field(description="SECID облигации")
    data: List[BondYieldRuoniaChartItem] = Field(
        default_factory=list,
        description="Нормализованные данные по датам",
    )
