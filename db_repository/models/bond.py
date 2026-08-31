"""Модели данных облигаций для таблиц БД (SQLModel).

Содержит Bond, BondSecurity, BondMarketData, BondMarketDataYield
для таблиц bonds, bondsecurity, bondmarketdata, bondmarketdatayield.
"""

from typing import Optional
from db_repository.models.bond_base import (
    BondBase,
    BondSecurityBase,
    BondMarketDataBase,
    BondMarketDataYieldBase)
from sqlmodel import Field as SQLField, Relationship
from sqlalchemy import UniqueConstraint
from db_repository.models.coupon import Coupon


class Bond(BondBase, table=True):

    __tablename__ = "bonds"

    __table_args__ = (
        UniqueConstraint(
            "secid",
            "boardid",
            name="uq_bonds_secid_boardid",
        ),
    )

    id: Optional[int] = SQLField(default=None, primary_key=True)

    coupons: list["Coupon"] = Relationship()

    security: Optional["BondSecurity"] = Relationship(
        back_populates="bond",
        sa_relationship_kwargs={"uselist": False}
    )

    marketdata: Optional["BondMarketData"] = Relationship(
        back_populates="bond",
        sa_relationship_kwargs={"uselist": False}
    )

    marketdata_yields: Optional["BondMarketDataYield"] = Relationship(
        back_populates="bond",
        sa_relationship_kwargs={"uselist": False}
    )


class BondSecurity(BondSecurityBase, table=True):

    __tablename__ = "bondsecurity"

    id: Optional[int] = SQLField(default=None, primary_key=True)

    bond: Optional["Bond"] = Relationship(
        back_populates="security"
    )

class BondMarketData(BondMarketDataBase, table=True):

    __tablename__ = "bondmarketdata"

    id: Optional[int] = SQLField(default=None, primary_key=True)

    bond: Optional["Bond"] = Relationship(
        back_populates="marketdata"
    )


class BondMarketDataYield(BondMarketDataYieldBase, table=True):

    __tablename__ = "bondmarketdatayield"

    id: Optional[int] = SQLField(default=None, primary_key=True)

    bond: Optional["Bond"] = Relationship(
        back_populates="marketdata_yields"
    )

