"""DTO информации об эмитенте для API (Pydantic)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmitentInfo(BaseModel):
    """Модель информации об эмитенте облигации для отдачи на фронтенд."""

    is_traded: Optional[int] = Field(None, description="Trading status (1 = traded, 0 = not traded)")
    emitent_title: Optional[str] = Field(None, description="Emitent title/name")
    emitent_inn: Optional[str] = Field(None, description="Emitent INN (tax ID)")
    type: Optional[str] = Field(None, description="Security type")
    cci_rating_companies: Optional[List[Dict[str, Any]]] = Field(
        None, description="Emitent ratings from MOEX API"
    )
