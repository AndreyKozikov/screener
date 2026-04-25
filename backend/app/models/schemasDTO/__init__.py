"""DTO (Pydantic) для взаимодействия с фронтендом и валидации API."""

from app.models.schemasDTO.bond_float_params_dto import BondFloatParamsDTO
from app.models.schemasDTO.bond_list_dto import BondDetail, BondListItem
from app.models.schemasDTO.bonds_dto import BondDetailDTO, BondScreenerDTO, round_float_for_api
from app.models.schemasDTO.coupons import (
    Coupon,
    CouponsBySecid,
    CouponsListResponse,
    MultipleCouponsResponse,
    Offer,
)
from app.models.schemasDTO.describe_dto import DescribeDTO
from app.models.schemasDTO.emitent_dto import EmitentInfo
from app.models.schemasDTO.filters import BondFilters
from app.models.schemasDTO.forecast_dto import ForecastDatesResponse
from app.models.schemasDTO.kbd_dto import KbdDataResponse, KbdDTO
from app.models.schemasDTO.keyrate_dto import KeyrateDTO
from app.models.schemasDTO.macro_rates_dto import CurrencyRateItem, MacroRatesDTO
from app.models.schemasDTO.responses import (
    BondsListResponse,
    ColumnMapping,
    DescriptionItem,
    ErrorResponse,
)
from app.models.schemasDTO.ruonia_dto import RuoniaDataResponse, RuoniaDTO
from app.models.schemasDTO.yield_ruonia_chart_dto import (
    BondYieldRuoniaChartItem,
    BondYieldRuoniaChartResponse,
)
from app.models.schemasDTO.price_history_dto import (
    BondPriceHistoryItem,
    BondPriceHistoryResponse,
)

__all__ = [
    "BondFloatParamsDTO",
    "BondDetail",
    "BondDetailDTO",
    "BondListItem",
    "BondScreenerDTO",
    "round_float_for_api",
    "Coupon",
    "CouponsBySecid",
    "CouponsListResponse",
    "MultipleCouponsResponse",
    "Offer",
    "DescribeDTO",
    "EmitentInfo",
    "BondFilters",
    "ForecastDatesResponse",
    "KbdDataResponse",
    "KbdDTO",
    "KeyrateDTO",
    "CurrencyRateItem",
    "MacroRatesDTO",
    "BondsListResponse",
    "ColumnMapping",
    "DescriptionItem",
    "ErrorResponse",
    "RuoniaDataResponse",
    "RuoniaDTO",
    "BondYieldRuoniaChartItem",
    "BondYieldRuoniaChartResponse",
    "BondPriceHistoryItem",
    "BondPriceHistoryResponse",
]
