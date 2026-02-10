"""Репозиторий для работы с таблицей currencyrate в БД.

Модуль содержит класс CurrencyrateRepository для чтения и записи данных
курсов валют ЦБ РФ через SQLModel: получение максимальной даты, пакетное
сохранение (upsert), выборка по дате и поиск ближайшей предыдущей записи.
"""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

from sqlalchemy import func, select
from sqlmodel import Session, create_engine

from app.models import DBcurrencyrate
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class CurrencyrateRepository:
    """Репозиторий для работы с таблицей currencyrate.

    Использует SQLModel Engine и Session. Не проверяет существование таблицы
    в runtime — таблица создаётся миграциями Alembic.

    Основные методы:
        get_max_date(): Максимальная дата в таблице (для инкрементальной загрузки).
        save_many(): Пакетный upsert записей currencyrate по полю dt.
        get_by_date(): Запись по дате или None.
        get_latest_on_or_before(): Ближайшая запись с датой <= указанной (для «предыдущих» курсов).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий для работы с таблицей currencyrate.

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
        """Возвращает максимальную дату (dt) в таблице currencyrate.

        Используется для определения начальной даты при инкрементальной
        загрузке: следующий период — (max_date + 1 день) до текущей даты.

        Returns:
            Объект date с максимальной датой в таблице или None, если таблица пуста.
        """
        with Session(self._engine) as session:
            stmt = select(func.max(DBcurrencyrate.dt))
            result = session.scalar(stmt)
            return result

    def save_many(self, records: List[DBcurrencyrate]) -> bool:
        """Выполняет пакетный upsert записей currencyrate по первичному ключу (dt).

        В рамках одной транзакции выполняет merge для каждой записи.
        Существующие даты обновляются, новые — вставляются.

        Args:
            records: Список объектов DBcurrencyrate для вставки/обновления.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not records:
            self.logger.debug("Нет записей currencyrate для вставки")
            return True
        data_log = get_data_update_logger()
        try:
            with Session(self._engine) as session:
                for row in records:
                    session.merge(row)
                session.commit()
            data_log.info(
                "[CURRENCY] В таблицу currencyrate записано записей: %s (база: %s)",
                len(records),
                self.db_path,
            )
            self.logger.info(
                "Успешно вставлено/обновлено %s записей в таблицу currencyrate",
                len(records),
            )
            return True
        except Exception as e:
            data_log.error(
                "[CURRENCY] Ошибка записи в таблицу currencyrate: %s", e, exc_info=True
            )
            self.logger.error(
                "Ошибка при записи данных currencyrate: %s", e, exc_info=True
            )
            return False

    def get_by_date(self, target_date: date) -> Optional[DBcurrencyrate]:
        """Возвращает запись currencyrate для указанной даты.

        Args:
            target_date: Дата для выборки.

        Returns:
            Объект DBcurrencyrate или None, если запись отсутствует.
        """
        with Session(self._engine) as session:
            stmt = select(DBcurrencyrate).where(DBcurrencyrate.dt == target_date)
            result = session.exec(stmt)
            row = result.first()
            if row is None:
                return None
            return row[0] if hasattr(row, "__getitem__") and len(row) == 1 else row

    def get_latest_on_or_before(self, target_date: date) -> Optional[DBcurrencyrate]:
        """Возвращает ближайшую запись с датой <= target_date (самую свежую из подходящих).

        Используется для отдачи «предыдущих» курсов, когда для запрошенной даты
        записи нет.

        Args:
            target_date: Верхняя граница даты (включительно).

        Returns:
            Объект DBcurrencyrate или None, если подходящих записей нет.
        """
        stmt = (
            select(DBcurrencyrate)
            .where(DBcurrencyrate.dt <= target_date)
            .order_by(DBcurrencyrate.dt.desc())
            .limit(1)
        )
        with Session(self._engine) as session:
            result = session.exec(stmt)
            row = result.first()
            if row is None:
                return None
            return row[0] if hasattr(row, "__getitem__") and len(row) == 1 else row
