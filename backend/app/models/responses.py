from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from .bond import BondListItem


class BondsListResponse(BaseModel):
    """Response for bonds list endpoint"""
    total: int
    filtered: int
    skip: int
    limit: int
    bonds: List[BondListItem]


class ColumnMapping(BaseModel):
    """Column name translation"""
    field_name: str
    display_name: str


class DescriptionItem(BaseModel):
    """Field description"""
    field_name: str
    title: str
    description: Optional[str] = None
    type: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str
    error_code: Optional[str] = None
