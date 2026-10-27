"""Client-side proxies for database operations owned by ``db_repository``."""

from typing import Optional

from app.repository.db.remote_repository import (
    BlogRepository,
    BondFloatParamsRepository,
    BondRatingsRepository,
    BondsRepository,
    CurrencyrateRepository,
    DBCoupon,
    DescribeRepository,
    EmissionDocumentRepository,
    EmitentEdisclosureRepository,
    EmitentsRepository,
    EventDetailRepository,
    ForecastRepository,
    KbdRepository,
    KeyrateRepository,
    RuoniaRepository,
    TradingHistoryRepository,
)

bonds_repo: Optional[BondsRepository] = None
history_repo: Optional[TradingHistoryRepository] = None
bond_float_repository: Optional[BondFloatParamsRepository] = None

def init_bonds_repository() -> None:
    global bonds_repo
    bonds_repo = BondsRepository()

def get_bonds_repository() -> BondsRepository:
    if bonds_repo is None:
        raise RuntimeError("BondsRepository not initialized. Call init_bonds_repository first.")
    return bonds_repo

def init_history_repository() -> None:
    global history_repo
    history_repo = TradingHistoryRepository()

def get_history_repository() -> TradingHistoryRepository:
    if history_repo is None:
        raise RuntimeError("HistoryRepository not initialized. Call init_history_repository first.")
    return history_repo

def init_bond_float_repository() -> None:
    global bond_float_repository
    bond_float_repository = BondFloatParamsRepository()

def get_bond_float_repository() -> BondFloatParamsRepository:
    if bond_float_repository is None:
        raise RuntimeError("BondFloatRepository not initialized. Call init_bond_float_repository first.")
    return bond_float_repository

__all__ = [
    "BlogRepository", "BondFloatParamsRepository", "BondRatingsRepository", "BondsRepository",
    "CurrencyrateRepository", "DBCoupon", "DescribeRepository", "EmissionDocumentRepository",
    "EmitentEdisclosureRepository", "EmitentsRepository", "EventDetailRepository",
    "ForecastRepository", "KbdRepository", "KeyrateRepository", "RuoniaRepository",
    "TradingHistoryRepository", "get_bond_float_repository", "get_bonds_repository",
    "get_history_repository", "init_bond_float_repository", "init_bonds_repository",
    "init_history_repository",
]
