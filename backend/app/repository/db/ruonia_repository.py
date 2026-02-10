"""Репозиторий для работы с таблицей ruonia в БД.

Модуль содержит класс RuoniaRepository для чтения и записи данных RUONIA
через SQLModel: получение максимальной даты, пакетное сохранение (upsert),
выборка по диапазону дат, подсчёт записей.
"""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

from sqlalchemy import func, select
from sqlmodel import Session, create_engine

from app.models import DBruonia
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class RuoniaRepository:
    """Репозиторий для работы с таблицей ruonia.

    Использует SQLModel Engine и Session. Не проверяет существование таблицы
    в runtime — таблица создаётся миграциями Alembic.

    Основные методы:
        get_max_date(): Максимальная дата в таблице (для инкрементальной загрузки).
        save_many(): Пакетный upsert записей RUONIA по полю dt.
        get_by_date_range(): Выборка записей по диапазону дат (from, till).
        get_count(): Общее количество записей в таблице.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий для работы с таблицей ruonia.

        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется backend/db/bonds.db.
        """
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger = logging.getLogger(__name__)

    def get_max_date(self) -> Optional[date]:
        """Возвращает максимальную дату (dt) в таблице ruonia.

        Используется для определения начальной даты при инкрементальной
        загрузке: следующий период — (max_date + 1 день) до текущей даты.

        Returns:
            Объект date с максимальной датой в таблице или None, если таблица пуста.
        """
        with Session(self._engine) as session:
            stmt = select(func.max(DBruonia.dt))
            result = session.scalar(stmt)
            return result

    def save_many(self, records: List[DBruonia]) -> bool:
        """Выполняет пакетный upsert записей RUONIA по первичному ключу (dt).

        В рамках одной транзакции выполняет merge для каждой записи.
        Существующие даты обновляются, новые — вставляются.

        Args:
            records: Список объектов DBruonia для вставки/обновления.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not records:
            self.logger.debug("Нет записей RUONIA для вставки")
            return True
        data_log = get_data_update_logger()
        try:
            with Session(self._engine) as session:
                for row in records:
                    session.merge(row)
                session.commit()
            data_log.info(
                "[RUONIA] В таблицу ruonia записано записей: %s (база: %s)",
                len(records),
                self.db_path,
            )
            self.logger.info("Успешно вставлено/обновлено %s записей в таблицу ruonia", len(records))
            return True
        except Exception as e:
            data_log.error("[RUONIA] Ошибка записи в таблицу ruonia: %s", e, exc_info=True)
            self.logger.error("Ошибка при записи данных RUONIA: %s", e, exc_info=True)
            return False

    def get_by_date_range(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[DBruonia]:
        """Возвращает записи RUONIA за диапазон дат.

        Если date_from или date_to не переданы, соответствующий фильтр не применяется.
        Сортировка по дате по убыванию (от новых к старым).

        Args:
            date_from: Начальная дата диапазона (включительно). None — без фильтра.
            date_to: Конечная дата диапазона (включительно). None — без фильтра.

        Returns:
            Список объектов DBruonia.
        """
        stmt = select(DBruonia)
        if date_from is not None:
            stmt = stmt.where(DBruonia.dt >= date_from)
        if date_to is not None:
            stmt = stmt.where(DBruonia.dt <= date_to)
        stmt = stmt.order_by(DBruonia.dt.desc())
        with Session(self._engine) as session:
            return list(session.exec(stmt).all())

    def get_count(self) -> int:
        """Возвращает общее количество записей в таблице ruonia.

        Returns:
            Число записей (0 если таблица пуста).
        """
        with Session(self._engine) as session:
            stmt = select(func.count()).select_from(DBruonia)
            result = session.scalar(stmt)
            return result or 0
