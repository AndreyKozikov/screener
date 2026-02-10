"""Модель таблицы describe_fields для хранения описаний полей.

Таблица используется для отдачи описаний полей (подсказки) на фронтенд
вместо файла describe.json. Секции: securities, marketdata.
"""

from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class DescribeField(SQLModel, table=True):
    """Запись описания поля для секции securities или marketdata.

    Attributes:
        id: Автоинкрементный первичный ключ.
        section: Секция (securities, marketdata).
        field_name: Имя поля (например SECID, YIELDATPREVWAPRICE).
        description: Текст описания поля.
    """

    __tablename__ = "describe_fields"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    section: str = SQLField(max_length=32, index=True)
    field_name: str = SQLField(max_length=128, index=True)
    description: str = SQLField()
