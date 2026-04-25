from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import date

class BondPriceHistoryItem(BaseModel):
    """Точка графика истории цены облигации."""
    model_config = ConfigDict(from_attributes=True)
    
    date: date
    open: Optional[float] = None

class BondPriceHistoryResponse(BaseModel):
    """Ответ API с историей цен облигации."""
    model_config = ConfigDict(from_attributes=True)
    
    secid: str
    data: List[BondPriceHistoryItem]
