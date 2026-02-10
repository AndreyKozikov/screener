"""Репозиторий для работы с таблицей keyrate в БД.

Модуль содержит класс KeyrateRepository для чтения и записи данных ключевой
ставки ЦБ РФ через SQLModel: получение максимальной даты, пакетное сохранение
(upsert), выборка по диапазону дат.
"""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

from sqlalchemy import func, select
from sqlmodel import Session, create_engine

from app.models import DBkeyrate
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class KeyrateRepository:
    """Репозиторий для работы с таблицей keyrate.

    Использует SQLModel Engine и Session. Не проверяет существование таблицы
    в runtime — таблица создаётся миграциями Alembic.

    Основные методы:
        get_max_date(): Максимальная дата в таблице (для инкрементальной загрузки).
        save_many(): Пакетный upsert записей keyrate по полю dt.
        get_by_date_range(): Выборка записей по диапазону дат (from_date, till_date).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий для работы с таблицей keyrate.

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
        """Возвращает максимальную дату (dt) в таблице keyrate.

        Используется для определения начальной даты при инкрементальной
        загрузке: следующий период — (max_date + 1 день) до текущей даты.

        Returns:
            Объект date с максимальной датой в таблице или None, если таблица пуста.
        """
        with Session(self._engine) as session:
            stmt = select(func.max(DBkeyrate.dt))
            result = session.scalar(stmt)
            return result

    def save_many(self, records: List[DBkeyrate]) -> bool:
        """Выполняет пакетный upsert записей keyrate по первичному ключу (dt).

        В рамках одной транзакции выполняет merge для каждой записи.
        Существующие даты обновляются, новые — вставляются.

        Args:
            records: Список объектов DBkeyrate для вставки/обновления.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not records:
            self.logger.debug("Нет записей keyrate для вставки")
            return True
        data_log = get_data_update_logger()
        try:
            with Session(self._engine) as session:
                for row in records:
                    session.merge(row)
                session.commit()
            data_log.info(
                "[KEYRATE] В таблицу keyrate записано записей: %s (база: %s)",
                len(records),
                self.db_path,
            )
            self.logger.info(
                "Успешно вставлено/обновлено %s записей в таблицу keyrate",
                len(records),
            )
            return True
        except Exception as e:
            data_log.error(
                "[KEYRATE] Ошибка записи в таблицу keyrate: %s", e, exc_info=True
            )
            self.logger.error(
                "Ошибка при записи данных keyrate: %s", e, exc_info=True
            )
            return False

    def get_by_date_range(
        self,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> List[DBkeyrate]:
        """Возвращает записи keyrate за диапазон дат.

        Если from_date или till_date не переданы, соответствующий фильтр
        не применяется. Сортировка по дате по убыванию (от новых к старым).

        Args:
            from_date: Начальная дата диапазона (включительно). None — без фильтра.
            till_date: Конечная дата диапазона (включительно). None — без фильтра.

        Returns:
            Список объектов DBkeyrate.
        """
        stmt = select(DBkeyrate)
        if from_date is not None:
            stmt = stmt.where(DBkeyrate.dt >= from_date)
        if till_date is not None:
            stmt = stmt.where(DBkeyrate.dt <= till_date)
        stmt = stmt.order_by(DBkeyrate.dt.desc())
        with Session(self._engine) as session:
            result = session.exec(stmt)
            rows = result.all()
            # session.exec(select(DBkeyrate)) returns Row tuples; take first column (entity)
            return [row[0] if hasattr(row, "__getitem__") and len(row) == 1 else row for row in rows]
