"""Create bond_trading_history table in separate DB history_db.db.

Revision ID: 014
Revises: 013
Create Date: 2026-02-08

Таблица bond_trading_history хранит исторические данные торгов по облигациям
из API Мосбиржи. Создаётся в отдельной базе backend/db/history_db.db.
Составной первичный ключ: (SECID, TRADEDATE, BOARDID).
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _history_db_path() -> Path:
    """Путь к history_db.db относительно корня backend."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    return backend_dir / "db" / "history_db.db"


def upgrade() -> None:
    """Создаёт таблицу bond_trading_history в БД history_db.db."""
    history_path = _history_db_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_url = f"sqlite:///{history_path}"

    # Подключаемся к history_db и создаём таблицу отдельно от основного Alembic connection
    history_engine = sa.create_engine(
        history_url,
        connect_args={"check_same_thread": False},
    )
    with history_engine.connect() as conn:
        conn.execute(
            sa.text("""
                CREATE TABLE IF NOT EXISTS bond_trading_history (
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
                )
            """)
        )
        conn.commit()
    history_engine.dispose()


def downgrade() -> None:
    """Удаляет таблицу bond_trading_history из history_db.db."""
    history_path = _history_db_path()
    if not history_path.exists():
        return
    history_url = f"sqlite:///{history_path}"
    history_engine = sa.create_engine(
        history_url,
        connect_args={"check_same_thread": False},
    )
    with history_engine.connect() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS bond_trading_history"))
        conn.commit()
    history_engine.dispose()
