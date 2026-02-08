"""Модели данных эмитентов облигаций.

Этот модуль содержит модели данных для представления информации об эмитентах
(организациях, выпускающих облигации). Используется для валидации и сериализации
данных из API MOEX и таблицы emitents в БД.
"""

from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField


class Emitent(SQLModel, table=True):
    """Модель эмитента для таблицы emitents в БД.

    Attributes:
        id: Первичный ключ (autoincrement).
        moex_id: ID эмитента в MOEX (emitent_id из JSON), UNIQUE.
        inn: ИНН эмитента (emitent_inn из JSON), UNIQUE.
        okpo: ОКПО эмитента (emitent_okpo из JSON).
        title: Наименование эмитента (emitent_title из JSON).
        type: Тип ценной бумаги эмитента (type из API MOEX, напр. ofz_bond, exchange_bond).
    """

    __tablename__ = "emitents"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    moex_id: Optional[int] = SQLField(default=None, unique=True)
    inn: Optional[str] = SQLField(default=None, max_length=32, unique=True)
    okpo: Optional[str] = SQLField(default=None, max_length=32)
    title: Optional[str] = SQLField(default=None)
    type: Optional[str] = SQLField(default=None, max_length=64)


class EmitentInfo(BaseModel):
    """Модель информации об эмитенте облигации.
    
    Содержит основные данные об организации-эмитенте, включая наименование,
    идентификационные номера, статус торговли и рейтинги. Данные берутся
    из API MOEX и таблицы emitents в БД.
    
    Attributes:
        is_traded: Статус торговли облигаций эмитента.
            1 - облигации эмитента торгуются на бирже,
            0 - облигации эмитента не торгуются.
        emitent_title: Наименование эмитента (полное название организации).
        emitent_inn: ИНН эмитента (идентификационный номер налогоплательщика).
        type: Тип ценной бумаги эмитента (например, "corporate_bond", "municipal_bond").
        cci_rating_companies: Список рейтингов эмитента от различных рейтинговых агентств.
            Каждый элемент списка - словарь с данными о рейтинге от MOEX API.
            Содержит информацию об агентстве, уровне рейтинга, дате присвоения и т.д.
    
    Note:
        Поле cci_rating_companies содержит данные в формате, полученном напрямую
        из API MOEX, поэтому используется гибкая структура Dict[str, Any] для
        размещения всех возможных полей рейтинга.
    """
    is_traded: Optional[int] = Field(None, description="Trading status (1 = traded, 0 = not traded)")
    emitent_title: Optional[str] = Field(None, description="Emitent title/name")
    emitent_inn: Optional[str] = Field(None, description="Emitent INN (tax ID)")
    type: Optional[str] = Field(None, description="Security type")
    cci_rating_companies: Optional[List[Dict[str, Any]]] = Field(None, description="Emitent ratings from MOEX API")

