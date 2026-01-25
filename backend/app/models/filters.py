from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class BondFilters(BaseModel):
    """Query parameters for filtering bonds"""
    # Coupon rate range
    coupon_min: Optional[float] = Field(None, ge=0, le=100, description="Min coupon rate %")
    coupon_max: Optional[float] = Field(None, ge=0, le=100, description="Max coupon rate %")
    
    # Yield to maturity range
    yield_min: Optional[float] = Field(None, ge=0, le=100, description="Min yield to maturity %")
    yield_max: Optional[float] = Field(None, ge=0, le=100, description="Max yield to maturity %")
    
    # Coupon yield to price range
    coupon_yield_min: Optional[float] = Field(None, ge=0, le=100, description="Min coupon yield to price %")
    coupon_yield_max: Optional[float] = Field(None, ge=0, le=100, description="Max coupon yield to price %")
    
    # Maturity date range
    matdate_from: Optional[date] = Field(None, description="Maturity date from (YYYY-MM-DD)")
    matdate_to: Optional[date] = Field(None, description="Maturity date to (YYYY-MM-DD)")
    
    # List level filter
    listlevel: Optional[List[int]] = Field(None, description="List levels (1, 2, 3, etc.)")
    
    # Currency filter (face unit)
    faceunit: Optional[List[str]] = Field(None, description="Currency face units (RUB, USD, EUR, etc.)")
    
    # Bond type filter (ID из bond_type_mapping)
    bondtype: Optional[List[int]] = Field(None, description="Bond type IDs (from bond_type_mapping: 1=exchange_bond, 2=ofz_bond, 3=corporate_bond, 4=municipal_bond, 5=subfederal_bond)")
    
    # Bond type 43 filter (ID из bond_type43_mapping)
    bondtype43: Optional[List[int]] = Field(None, description="Bond type43 IDs (from bond_type43_mapping: 1=Амортизируемые облигации, 2=Валютные облигации, 3=Конвертируемые облигации, 4=Линкер/облигации с индексируемым, 5=Структурная облигация, 6=Фикс с известным купоном, 7=Фикс с неизвестным купоном, 8=Флоатер)")
    
    # Rating range filter
    rating_min: Optional[str] = Field(None, description="Minimum rating (AAA, AA+, AA, AA-, A+, etc.)")
    rating_max: Optional[str] = Field(None, description="Maximum rating (AAA, AA+, AA, AA-, A+, etc.)")
    
    # Search
    search: Optional[str] = Field(None, description="Search in SECID, SHORTNAME, SECNAME")
    
    # Pagination
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Max records to return")
