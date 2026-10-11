from datetime import date
from pydantic import BaseModel, Field


class InflationDateFilter(BaseModel):
    from_date: date = Field(default=None, validation_alias="from_date")
    till_date: date = Field(default=None, validation_alias="till_date")