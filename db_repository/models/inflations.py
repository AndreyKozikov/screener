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
        validation_alias="observed_annual_inflation"
    )

    expected_annual_inflation: Optional[float] = SQLField(
        default=None,
        validation_alias="expected_annual_inflation"
    )

    expected_five_year_inflation: Optional[float] = SQLField(
        default=None,
        validation_alias="expected_five_year_inflation"
    )

    expectations_index: Optional[float] = SQLField(
        default=None,
        validation_alias="expectations_index"
    )

class InflationExpectations(InflationExpectationsBase, table=True):
    __tablename__ = "inflation_expectations"