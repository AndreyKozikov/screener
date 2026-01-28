"""Модели данных эмитентов облигаций.

Этот модуль содержит модели данных для представления информации об эмитентах
(организациях, выпускающих облигации). Используется для валидации и сериализации
данных из bonds_emitent.json и API MOEX.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EmitentInfo(BaseModel):
    """Модель информации об эмитенте облигации.
    
    Содержит основные данные об организации-эмитенте, включая наименование,
    идентификационные номера, статус торговли и рейтинги. Данные берутся
    из файла bonds_emitent.json и API MOEX.
    
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

