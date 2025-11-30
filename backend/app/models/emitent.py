from typing import Optional
from pydantic import BaseModel, Field


class EmitentInfo(BaseModel):
    """Emitent information model"""
    is_traded: Optional[int] = Field(None, description="Trading status (1 = traded, 0 = not traded)")
    emitent_title: Optional[str] = Field(None, description="Emitent title/name")
    emitent_inn: Optional[str] = Field(None, description="Emitent INN (tax ID)")
    type: Optional[str] = Field(None, description="Security type")

