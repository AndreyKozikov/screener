"""DTO для отдачи данных среднесрочного прогноза Банка России на фронтенд.

Содержит ForecastDatesResponse — список доступных дат прогнозов (YYYY-MM-DD),
соответствует интерфейсу ForecastDatesResponse на фронтенде.
"""

from typing import List

from pydantic import BaseModel, Field


class ForecastDatesResponse(BaseModel):
    """Ответ API со списком дат, по которым доступны прогнозы в БД.

    Фронтенд использует эти даты для выпадающего списка на странице
    «Среднесрочный прогноз Банка России».
    """

    dates: List[str] = Field(
        description="Список дат в формате YYYY-MM-DD, отсортированных от новых к старым",
    )
