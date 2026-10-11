from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class InflationDateFilter(BaseModel):
    from_date: Optional[date] = Field(default=None, validation_alias="from")
    till_date: Optional[date] = Field(default=None, validation_alias="till")