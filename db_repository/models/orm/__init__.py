"""SQLModel table definitions owned by the database microservice."""

from db_repository.models.bond import Bond, BondMarketData, BondMarketDataYield, BondSecurity
from db_repository.models.emitent import Emitent
from db_repository.models.ratings import BondRating, EmitentRating, RatingAgency
from db_repository.models.orm.blog import BlogArticle
from db_repository.models.orm.bond_float_params import BondFloatParams
from db_repository.models.orm.currencyrate import DBcurrencyrate
from db_repository.models.orm.describe import DescribeField
from db_repository.models.orm.emission_document import EmissionDocument
from db_repository.models.orm.emitent_edisclosure import EmitentEdisclosure
from db_repository.models.orm.event_detail import EventDetail
from db_repository.models.orm.forecast import (
    Forecast,
    ForecastBalance,
    ForecastIndicatorName,
    ForecastMainIndicators,
)
from db_repository.models.orm.kbd import DBkbd
from db_repository.models.orm.keyrate import DBkeyrate
from db_repository.models.orm.ruonia import DBruonia
from db_repository.models.orm.trading_history import TradingHistoryRecord

__all__ = [
    "BlogArticle",
    "Bond",
    "BondFloatParams",
    "BondMarketData",
    "BondMarketDataYield",
    "BondRating",
    "BondSecurity",
    "DBcurrencyrate",
    "DBkbd",
    "DBkeyrate",
    "DBruonia",
    "DescribeField",
    "Emitent",
    "EmitentEdisclosure",
    "EmitentRating",
    "EmissionDocument",
    "EventDetail",
    "Forecast",
    "ForecastBalance",
    "ForecastIndicatorName",
    "ForecastMainIndicators",
    "RatingAgency",
    "TradingHistoryRecord",
]
