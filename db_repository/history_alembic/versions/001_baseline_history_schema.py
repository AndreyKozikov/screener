"""Baseline current history database schema

Revision ID: 001_baseline_history_schema
Revises:
Create Date: 2026-11-08

Baseline текущей схемы. Создан по фактическому состоянию базы.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "001_baseline_history_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE bond_trading_history (
                    secid VARCHAR(36) NOT NULL,
                    tradedate DATE NOT NULL,
                    boardid VARCHAR(12) NOT NULL,
                    numtrades REAL,
                    value REAL,
                    legalcloseprice REAL,
                    accint REAL,
                    yieldclose REAL,
                    "open" REAL,
                    volume REAL,
                    duration REAL,
                    yieldatwap REAL,
                    iricpiclose REAL,
                    couponpercent REAL,
                    couponvalue REAL,
                    facevalue REAL,
                    yieldtooffer REAL,
                    yieldlastcoupon REAL,
                    calloptionyield REAL,
                    calloptionduration REAL,
                    zspread REAL,
                    buybackdate DATE,
                    lasttradedate DATE,
                    putoptiondate DATE,
                    dateyieldfromissuer DATE,
                    trade_session_date DATE,
                    PRIMARY KEY (secid, tradedate, boardid)
                )"""
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "bond_trading_history"')
