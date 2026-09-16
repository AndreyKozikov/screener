from typing import Optional
from sqlmodel import SQLModel, Field as SQLField
from datetime import date


class IpcBase(SQLModel):
    record_data: date = SQLField(
        primary_key=True,
        validation_alias="record_data",
        description="Дата опубликования данных"
    )

    ipc: Optional[float] = SQLField(
        default=None,
        validation_alias="ipc",
        description="Индекс потребительских цен"
    )

    food_ipc: Optional[float] = SQLField(
        default=None,
        validation_alias="food_ipc",
        description="Индекс потребительских цен продовольственных товаров"
    )

    non_food_ipc: Optional[float] = SQLField(
        default=None,
        validation_alias="non_food_ipc",
        description="Индекс потребительских цен непродовольственных товаров"
    )

    services_ipc: Optional[float] = SQLField(
        default=None,
        validation_alias="services_ipc",
        description="Индекс потребительских цен на услуги"
    )


class Ipc(IpcBase, table=True):
    __tablename__ = "ipc_table"


class IpcWeeklyBase(SQLModel):
    start_date: date = SQLField(
        primary_key=True,
        validation_alias="start_data",
        description="Начальная дача отчетного периода"
    )

    end_date: date = SQLField(
        validation_alias="end_data",
        description="Конечная дата отчетного периода"
    )

    ipc_weekly: Optional[float] = SQLField(
        default=None,
        validation_alias="ipc_weekly",
        description="Значение недельного индекса потребительских цен"
    )

    source_url: Optional[str] = SQLField(
        default=None,
        validation_alias="source_url",
        description="Ссылка на отчет"
    )


class IpcWeekly(IpcWeeklyBase, table=True):
    __tablename__ = "ipc_weekly"
