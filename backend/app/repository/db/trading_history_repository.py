"""Репозиторий для таблицы истории торгов в БД history_db.db.

Потокобезопасная запись (lock + bulk INSERT OR REPLACE) и параллельное чтение
последней даты (NullPool — отдельное соединение на поток).
"""

import logging
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine, select

from app.models.trading_history import TradingHistoryRecord
from config.paths import HISTORY_DB_PATH


def _record_to_row(rec: TradingHistoryRecord) -> Dict[str, Any]:
    """Преобразует TradingHistoryRecord в словарь для bulk INSERT (даты — строки)."""
    def _d(d: Optional[date]) -> Optional[str]:
        return d.isoformat() if d else None
    return {
        "secid": rec.secid,
        "tradedate": _d(rec.tradedate),
        "boardid": rec.boardid,
        "numtrades": rec.numtrades,
        "value": rec.value,
        "legalcloseprice": rec.legalcloseprice,
        "accint": rec.accint,
        "yieldclose": rec.yieldclose,
        "open": rec.open,
        "volume": rec.volume,
        "duration": rec.duration,
        "yieldatwap": rec.yieldatwap,
        "iricpiclose": rec.iricpiclose,
        "couponpercent": rec.couponpercent,
        "couponvalue": rec.couponvalue,
        "facevalue": rec.facevalue,
        "yieldtooffer": rec.yieldtooffer,
        "yieldlastcoupon": rec.yieldlastcoupon,
        "calloptionyield": rec.calloptionyield,
        "calloptionduration": rec.calloptionduration,
        "zspread": rec.zspread,
        "buybackdate": _d(rec.buybackdate),
        "lasttradedate": _d(rec.lasttradedate),
        "putoptiondate": _d(rec.putoptiondate),
        "dateyieldfromissuer": _d(rec.dateyieldfromissuer),
        "trade_session_date": _d(rec.trade_session_date),
    }


_INSERT_SQL = text("""
    INSERT OR REPLACE INTO bond_trading_history (
        secid, tradedate, boardid, numtrades, value, legalcloseprice, accint,
        yieldclose, "open", volume, duration, yieldatwap, iricpiclose,
        couponpercent, couponvalue, facevalue, yieldtooffer, yieldlastcoupon,
        calloptionyield, calloptionduration, zspread,
        buybackdate, lasttradedate, putoptiondate, dateyieldfromissuer, trade_session_date
    ) VALUES (
        :secid, :tradedate, :boardid, :numtrades, :value, :legalcloseprice, :accint,
        :yieldclose, :open, :volume, :duration, :yieldatwap, :iricpiclose,
        :couponpercent, :couponvalue, :facevalue, :yieldtooffer, :yieldlastcoupon,
        :calloptionyield, :calloptionduration, :zspread,
        :buybackdate, :lasttradedate, :putoptiondate, :dateyieldfromissuer, :trade_session_date
    )
""")


class TradingHistoryRepository:
    """Репозиторий для работы с таблицей bond_trading_history в history_db.db.

    Запись — под блокировкой, одним bulk INSERT OR REPLACE. Чтение — параллельно
    (NullPool даёт отдельное соединение на поток, SQLite поддерживает много читателей).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий и движок БД истории торгов.

        Args:
            db_path: Путь к файлу history_db.db. Если не указан,
                используется config.paths.HISTORY_DB_PATH.
        """
        self.db_path = Path(db_path) if db_path is not None else Path(HISTORY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            echo=False,
        )
        self._write_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def get_last_tradedate(self, secid: str) -> Optional[date]:
        """Возвращает максимальную дату торгов (TRADEDATE) по облигации.

        Args:
            secid: Идентификатор ценной бумаги (SECID).

        Returns:
            Дата последней записи в истории по данному secid или None,
            если записей нет или произошла ошибка.
        """
        try:
            with Session(self._engine) as session:
                stmt = (
                    select(TradingHistoryRecord.tradedate)
                    .where(TradingHistoryRecord.secid == secid.strip())
                    .order_by(TradingHistoryRecord.tradedate.desc())
                    .limit(1)
                )
                row = session.exec(stmt).first()
                return row if isinstance(row, date) else None
        except Exception as e:
            self.logger.warning(
                "Ошибка при получении последней даты торгов для %s: %s",
                secid,
                e,
                exc_info=True,
            )
            return None

    def save_records(self, records: List[TradingHistoryRecord]) -> int:
        """Потокобезопасно сохраняет записи одним bulk INSERT OR REPLACE.

        При конфликте по (secid, tradedate, boardid) строка обновляется.
        Одна транзакция и executemany — быстрее, чем merge по одной записи.

        Args:
            records: Список объектов TradingHistoryRecord для сохранения.

        Returns:
            Количество успешно записанных записей.

        Raises:
            Exception: При критической ошибке БД (логируется и пробрасывается).
        """
        if not records:
            return 0
        rows = [_record_to_row(r) for r in records]
        with self._write_lock:
            try:
                with self._engine.connect() as conn:
                    conn.execute(_INSERT_SQL, rows)
                    conn.commit()
                self.logger.debug(
                    "Сохранено записей истории торгов: %s",
                    len(records),
                )
                return len(records)
            except Exception as e:
                self.logger.error(
                    "Ошибка при сохранении истории торгов: %s",
                    e,
                    exc_info=True,
                )
                raise

    def ensure_table_exists(self) -> None:
        """Создаёт таблицу bond_trading_history в history_db, если её нет.

        Вызывается при инициализации сервиса. Миграции Alembic для
        history_db выполняются отдельно; этот метод — страховка для dev.
        """
        with self._write_lock:
            TradingHistoryRecord.__table__.create(
                self._engine, checkfirst=True
            )
