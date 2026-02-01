"""Репозиторий для работы с таблицей kbd (кривая бескупонной доходности).

Использует SQLModel и модель DBkbd. Отвечает только за чтение и запись данных;
создание таблицы — через Alembic. Получение данных с API и преобразование — вне репозитория.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, create_engine, func, select

from app.models.kbd_model import DBkbd
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


# Колонки для выборки «только для фронта» (без term_30_0)
FRONTEND_COLUMNS = (
    "date", "time",
    "term_0_25", "term_0_5", "term_0_75", "term_1_0",
    "term_2_0", "term_3_0", "term_5_0", "term_7_0",
    "term_10_0", "term_15_0", "term_20_0",
)


class KbdRepository:
    """Репозиторий для таблицы kbd. Работа через SQLModel Session."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger = logging.getLogger(__name__)

    def save_kbd_records(self, records: List[DBkbd]) -> bool:
        """Сохраняет записи КБД в таблицу kbd (merge по первичному ключу)."""
        if not records:
            self.logger.warning("Нет данных для вставки")
            return True
        data_log = get_data_update_logger()
        try:
            with Session(self._engine) as session:
                for row in records:
                    session.merge(row)
                session.commit()
            data_log.info(
                "[KBD] В таблицу kbd записано записей: %s (база: %s)",
                len(records),
                self.db_path,
            )
            self.logger.info("Успешно вставлено/обновлено %s записей в таблицу kbd", len(records))
            return True
        except Exception as e:
            data_log.error("[KBD] Ошибка записи в таблицу kbd: %s", e, exc_info=True)
            self.logger.error("Ошибка при записи в таблицу kbd: %s", e, exc_info=True)
            return False

    def get_last_kbd_date(self) -> Optional[datetime]:
        """Возвращает максимальную дату в таблице kbd (для инкрементальной загрузки)."""
        try:
            with Session(self._engine) as session:
                stmt = select(func.max(DBkbd.date))
                result = session.exec(stmt).one()
            if not result:
                return None
            return datetime.strptime(result, "%Y-%m-%d")
        except Exception as e:
            self.logger.debug("get_last_kbd_date: %s", e)
            return None

    def get_kbd_data(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        for_frontend: bool = False,
    ) -> List[Dict[str, Any]]:
        """Выбирает данные из kbd с фильтром по датам. Без проверки существования таблицы."""
        with Session(self._engine) as session:
            stmt = select(DBkbd).order_by(DBkbd.date.desc())
            if date_from:
                try:
                    d = datetime.strptime(date_from, "%d.%m.%Y").strftime("%Y-%m-%d")
                    stmt = stmt.where(DBkbd.date >= d)
                except ValueError:
                    self.logger.warning("Неверный формат date_from: %s", date_from)
            if date_to:
                try:
                    d = datetime.strptime(date_to, "%d.%m.%Y").strftime("%Y-%m-%d")
                    stmt = stmt.where(DBkbd.date <= d)
                except ValueError:
                    self.logger.warning("Неверный формат date_to: %s", date_to)
            rows = session.exec(stmt).all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            d = row.model_dump()
            if for_frontend:
                d = {k: d.get(k) for k in FRONTEND_COLUMNS if k in d}
            out.append(d)
        self.logger.debug(
            "Выбрано %s записей из таблицы kbd (date_from=%s, date_to=%s)",
            len(out), date_from, date_to,
        )
        return out

