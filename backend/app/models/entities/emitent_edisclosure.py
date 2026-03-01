"""Модель маппинга эмитента на e-disclosure.ru (SQLModel)."""

from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class EmitentEdisclosure(SQLModel, table=True):
    """Соответствие emitent_id (FK на emitents.id) и edisclosure_id (ID на e-disclosure.ru).

    Attributes:
        id: Первичный ключ (autoincrement).
        emitent_id: FK на emitents.id, UNIQUE — один маппинг на эмитента.
        edisclosure_id: ID компании на сайте e-disclosure.ru.
    """

    __tablename__ = "emitent_edisclosure"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    emitent_id: int = SQLField(foreign_key="emitents.id", unique=True, nullable=False)
    edisclosure_id: int = SQLField(nullable=False)
