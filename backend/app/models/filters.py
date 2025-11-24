from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class BondFilters(BaseModel):
    """Query parameters for filtering bonds"""
    # Coupon rate range
    coupon_min: Optional[float] = Field(None, ge=0, le=100, description="Min coupon rate %")
    coupon_max: Optional[float] = Field(None, ge=0, le=100, description="Max coupon rate %")
    
    # Maturity date range
    matdate_from: Optional[date] = Field(None, description="Maturity date from (YYYY-MM-DD)")
    matdate_to: Optional[date] = Field(None, description="Maturity date to (YYYY-MM-DD)")
    
    # List level filter
    listlevel: Optional[List[int]] = Field(None, description="List levels (1, 2, 3, etc.)")
    
    # Currency filter (face unit)
    faceunit: Optional[List[str]] = Field(None, description="Currency face units (RUB, USD, EUR, etc.)")
    
    # Search
    search: Optional[str] = Field(None, description="Search in SECID, SHORTNAME, SECNAME")
    
    # Pagination
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Max records to return")
