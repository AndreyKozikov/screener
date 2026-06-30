"""Репозитории для работы только с базой данных (SQLite).

Содержит классы для таблиц bonds, coupons, kbd, ruonia, keyrate, currencyrate,
describe_fields и константы для репозиториев.
"""

from pathlib import Path
from typing import Optional

from app.repository.db.bond_ratings_repository import BondRatingsRepository
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.constants import RATINGS_ORDER
from app.repository.db.currencyrate_repository import CurrencyrateRepository
from app.repository.db.db_coupon import DBCoupon
from app.repository.db.db_kbd import KbdRepository
from app.repository.db.describe_repository import DescribeRepository
from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.db.forecast_repository import ForecastRepository
from app.repository.db.keyrate_repository import KeyrateRepository
from app.repository.db.ruonia_repository import RuoniaRepository
from app.repository.db.trading_history_repository import TradingHistoryRepository
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository

bonds_repo: Optional[BondsRepository] = None
history_repo: Optional[TradingHistoryRepository] = None

def init_bonds_repository(db_path: Path) -> None:
    global bonds_repo
    bonds_repo = BondsRepository(db_path=db_path)

def get_bonds_repository() -> BondsRepository:
    if bonds_repo is None:
        raise RuntimeError("BondsRepository not initialized. Call init_bonds_repository first.")
    return bonds_repo

def init_history_repository(db_path: Path) -> None:
    global history_repo
    history_repo = TradingHistoryRepository(db_path=db_path)

def get_history_repository() -> TradingHistoryRepository:
    if history_repo is None:
        raise RuntimeError("HistoryRepository not initialized. Call init_history_repository first.")
    return history_repo

def init_bond_float_repository(db_path: Path) -> None:
    global bond_float_repository
    bond_float_repository = BondFloatParamsRepository(db_path=db_path)

def get_bond_float_repository() -> BondFloatParamsRepository:
    if bond_float_repository is None:
        raise RuntimeError("BondFloatRepository not initialized. Call init_bond_float_repository first.")
    return bond_float_repository

