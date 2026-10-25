from typing import Optional

from pydantic import Field, BaseModel
from datetime import date

class IpcDateFilter(BaseModel):
    from_date: date = Field(default=None, validation_alias="from_date")
    till_date: date = Field(default=None, validation_alias="till_date")


class IpcWeeklyDTO(BaseModel):
    start_date: date = Field(
        validation_alias="start_date",
        description="Начальная дача отчетного периода"
    )

    end_date: date = Field(
        validation_alias="end_date",
        description="Конечная дата отчетного периода"
    )

    ipc_weekly: Optional[float] = Field(
        default=None,
        validation_alias="ipc_weekly",
        description="Значение недельного индекса потребительских цен"
    )
