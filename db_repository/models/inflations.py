from typing import Optional
from sqlmodel import SQLModel, Field as SQLField
from datetime import date

class InflationExpectationsBase(SQLModel):
    recorddata: date = SQLField(
        primary_key=True,
        validation_alias="recorddata"
    )

    observed_annual_inflation: Optional[float] = SQLField(
        default=None,
        validation_alias="observed_annual_inflation",
        description="Наблюдаемая годовая инфляция"

    )

    expected_annual_inflation: Optional[float] = SQLField(
        default=None,
        validation_alias="expected_annual_inflation",
        description="Ожидаемая годовая инфляция"
    )

    expected_five_year_inflation: Optional[float] = SQLField(
        default=None,
        validation_alias="expected_five_year_inflation",
        description="Ожидаемая 5-летняя инфляция"

    )

    expectations_index: Optional[float] = SQLField(
        default=None,
        validation_alias="expectations_index",
        description="Индекс ожиданий в пунктах"
    )

class InflationExpectations(InflationExpectationsBase, table=True):
    # Ожидаемая инфляция
    __tablename__ = "inflation_expectations"



class InflationDataBase(SQLModel):

    record_date: date = SQLField(
        primary_key=True,
        validation_alias="record_date",
        description="Дата опубликования записи"
    )

    trend_inflation_3y: Optional[float] = SQLField(
        default=None,
        validation_alias="trend_inflation_3y",
        description="Оценка трендовой инфляции (3-летнее скользящее окно)"
    )

    trend_inflation_5y: Optional[float] = SQLField(
        default=None,
        validation_alias="trend_inflation_5y",
        description="Оценка трендовой инфляции (5-летнее скользящее окно)"
    )

    modified_core_inflation: Optional[float] = SQLField(
        default=None,
        validation_alias="modified_core_inflation",
        description="Модифицированный показатель базовой инфляции, рассчитанный на основе метода усечения"
    )


class InflationData(InflationDataBase, table=True):
    __tablename__="inflation_data"