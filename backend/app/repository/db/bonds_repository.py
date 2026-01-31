"""Репозиторий для запросов и фильтрации облигаций из базы данных.

Модуль содержит класс BondsRepository для работы с таблицей bonds через
SQLModel API: выборка с фильтрами, подсчёт, пакетное сохранение (upsert).
Все операции выполняются через SQLModel/SQLAlchemy API без текстовых SQL.
"""

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, and_
from sqlmodel import Session, create_engine, select

from app.models.bond import Bond
from app.models.filters import BondFilters
from app.repository.db.constants import RATINGS_ORDER
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class BondsRepository:
    """Репозиторий для запросов и фильтрации облигаций из базы данных.

    Использует SQLModel Engine и Session для работы с таблицей bonds.
    Не выполняет расчётов — принимает готовые объекты Bond от bond_transformer.

    Основные методы:
        save_bonds(): Пакетный upsert облигаций по SECID.
        select(): Выборка с динамическими фильтрами через SQLModel API.
        count(): Подсчёт с теми же фильтрами.
        count_bonds(): Общее количество для API (без фильтров по рейтингу).
        refresh(): Сохранение списка Bond (вызов save_bonds).
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Инициализирует репозиторий для работы с облигациями.

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

    def save_bonds(self, bonds: List[Bond]) -> bool:
        """Выполняет пакетный upsert облигаций по SECID.

        Принимает список готовых объектов Bond (расчёты выполняются в
        bond_transformer). В рамках одной транзакции выполняет merge
        по первичному ключу (SECID).

        Args:
            bonds: Список объектов Bond для вставки/обновления.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not bonds:
            self.logger.warning("Нет данных для вставки")
            return True
        data_log = get_data_update_logger()
        try:
            with Session(self._engine) as session:
                for bond in bonds:
                    session.merge(bond)
                session.commit()
            data_log.info(
                "[API /bonds/refresh] В таблицу bonds записано записей: %s (база: %s)",
                len(bonds),
                self.db_path,
            )
            self.logger.info("Успешно вставлено/обновлено %s записей в таблицу bonds", len(bonds))
            return True
        except Exception as e:
            data_log.error("[API /bonds/refresh] Ошибка INSERT в таблицу bonds: %s", e, exc_info=True)
            self.logger.error("Ошибка при вставке данных в таблицу bonds: %s", e, exc_info=True)
            return False

    def _build_where_conditions(
        self,
        *,
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        rating_min: Optional[str] = None,
        rating_max: Optional[str] = None,
        exclude_spob: bool = False,
    ) -> Any:
        """Формирует комбинированное условие WHERE для запросов к Bond.

        Returns:
            Выражение SQLAlchemy (and_ из условий) или True (1=1).
        """
        conditions: List[Any] = []
        if coupon_percent_min is not None:
            conditions.append(Bond.coupon_percent >= coupon_percent_min)
        if coupon_percent_max is not None:
            conditions.append(Bond.coupon_percent <= coupon_percent_max)
        if yield_to_maturity_min is not None:
            conditions.append(Bond.yield_to_maturity >= yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            conditions.append(Bond.yield_to_maturity <= yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            conditions.append(Bond.coupon_yield_to_price >= coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            conditions.append(Bond.coupon_yield_to_price <= coupon_yield_to_price_max)
        if maturity_date_from is not None:
            conditions.append(Bond.maturity_date >= maturity_date_from)
        if maturity_date_to is not None:
            conditions.append(Bond.maturity_date <= maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            conditions.append(Bond.listing_level.in_(listlevel))
        if currency is not None and len(currency) > 0:
            conditions.append(Bond.currency.in_(currency))
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            conditions.append(Bond.bond_type.in_(bond_type_ids))
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            conditions.append(Bond.bond_kind.in_(bond_kind_ids))
        ratings_in_range = self._rating_range_list(rating_min, rating_max)
        if ratings_in_range:
            conditions.append(Bond.rating.isnot(None))
            conditions.append(Bond.rating != "")
            conditions.append(func.upper(func.trim(Bond.rating)).in_([r.upper() for r in ratings_in_range]))
        if exclude_spob:
            conditions.append(
                or_(
                    Bond.boardid.is_(None),
                    func.upper(func.trim(Bond.boardid)) != "SPOB",
                )
            )
        if not conditions:
            return True
        return and_(*conditions)

    def _rating_range_list(
        self,
        rating_min: Optional[str],
        rating_max: Optional[str],
    ) -> Optional[List[str]]:
        """Возвращает список рейтингов в диапазоне [rating_min, rating_max] по шкале RATINGS_ORDER.

        Returns:
            Список строк рейтингов или None, если фильтр не применим.
        """
        if rating_min is None and rating_max is None:
            return None
        try:
            idx_start = RATINGS_ORDER.index(rating_min.upper()) if rating_min else 0
            idx_end = RATINGS_ORDER.index(rating_max.upper()) if rating_max else len(RATINGS_ORDER) - 1
        except ValueError:
            self.logger.warning("Рейтинг не найден в шкале RATINGS_ORDER: min=%s, max=%s", rating_min, rating_max)
            return None
        low = min(idx_start, idx_end)
        high = max(idx_start, idx_end)
        return RATINGS_ORDER[low : high + 1]

    def select(
        self,
        filters: Optional[BondFilters] = None,
        *,
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        rating_min: Optional[str] = None,
        rating_max: Optional[str] = None,
        exclude_spob: bool = False,
    ) -> List[Bond]:
        """Выборка облигаций с динамическими фильтрами через SQLModel API.

        Условия формируются через _build_where_conditions; запрос выполняется
        через select(Bond).where(...). Возвращает список объектов Bond.

        Args:
            filters: Объект BondFilters; при наличии подставляется вместо
                прямых параметров.
            Остальные аргументы — прямые параметры фильтрации (как в BondFilters).

        Returns:
            Список объектов Bond, удовлетворяющих фильтрам.

        Raises:
            Exception: При ошибке работы с БД.
        """
        if filters is not None:
            coupon_percent_min = filters.coupon_min
            coupon_percent_max = filters.coupon_max
            yield_to_maturity_min = filters.yield_min
            yield_to_maturity_max = filters.yield_max
            coupon_yield_to_price_min = filters.coupon_yield_min
            coupon_yield_to_price_max = filters.coupon_yield_max
            maturity_date_from = filters.matdate_from.isoformat() if filters.matdate_from else None
            maturity_date_to = filters.matdate_to.isoformat() if filters.matdate_to else None
            listlevel = filters.listlevel
            currency = filters.faceunit
            rating_min = filters.rating_min
            rating_max = filters.rating_max

        where = self._build_where_conditions(
            coupon_percent_min=coupon_percent_min,
            coupon_percent_max=coupon_percent_max,
            yield_to_maturity_min=yield_to_maturity_min,
            yield_to_maturity_max=yield_to_maturity_max,
            coupon_yield_to_price_min=coupon_yield_to_price_min,
            coupon_yield_to_price_max=coupon_yield_to_price_max,
            maturity_date_from=maturity_date_from,
            maturity_date_to=maturity_date_to,
            listlevel=listlevel,
            currency=currency,
            bond_type_ids=bond_type_ids,
            bond_kind_ids=bond_kind_ids,
            rating_min=rating_min,
            rating_max=rating_max,
            exclude_spob=exclude_spob,
        )
        stmt = select(Bond).where(where)
        try:
            with Session(self._engine) as session:
                result = list(session.exec(stmt).all())
            self.logger.debug("Выбрано %s записей из таблицы bonds с применением фильтров", len(result))
            return result
        except Exception as e:
            self.logger.error("Ошибка при select: %s", e, exc_info=True)
            raise

    def count(
        self,
        filters: Optional[BondFilters] = None,
        *,
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        rating_min: Optional[str] = None,
        rating_max: Optional[str] = None,
        exclude_spob: bool = False,
    ) -> int:
        """Подсчёт облигаций с теми же фильтрами, что и select.

        Returns:
            Количество записей Bond, удовлетворяющих условиям.
        """
        if filters is not None:
            coupon_percent_min = filters.coupon_min
            coupon_percent_max = filters.coupon_max
            yield_to_maturity_min = filters.yield_min
            yield_to_maturity_max = filters.yield_max
            coupon_yield_to_price_min = filters.coupon_yield_min
            coupon_yield_to_price_max = filters.coupon_yield_max
            maturity_date_from = filters.matdate_from.isoformat() if filters.matdate_from else None
            maturity_date_to = filters.matdate_to.isoformat() if filters.matdate_to else None
            listlevel = filters.listlevel
            currency = filters.faceunit
            rating_min = filters.rating_min
            rating_max = filters.rating_max

        where = self._build_where_conditions(
            coupon_percent_min=coupon_percent_min,
            coupon_percent_max=coupon_percent_max,
            yield_to_maturity_min=yield_to_maturity_min,
            yield_to_maturity_max=yield_to_maturity_max,
            coupon_yield_to_price_min=coupon_yield_to_price_min,
            coupon_yield_to_price_max=coupon_yield_to_price_max,
            maturity_date_from=maturity_date_from,
            maturity_date_to=maturity_date_to,
            listlevel=listlevel,
            currency=currency,
            bond_type_ids=bond_type_ids,
            bond_kind_ids=bond_kind_ids,
            rating_min=rating_min,
            rating_max=rating_max,
            exclude_spob=exclude_spob,
        )
        stmt = select(func.count()).select_from(Bond).where(where)
        try:
            with Session(self._engine) as session:
                return int(session.exec(stmt).one())
        except Exception as e:
            self.logger.error("Ошибка при count: %s", e, exc_info=True)
            raise

    def count_bonds(
        self,
        *,
        exclude_spob: bool = False,
    ) -> int:
        """Возвращает общее количество облигаций в таблице bonds (без фильтров по рейтингу и др.).

        Используется для поля total в ответе API.

        Args:
            exclude_spob: Исключить облигации с режимом торгов SPOB.

        Returns:
            Количество записей в таблице bonds.
        """
        where = True
        if exclude_spob:
            where = or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "SPOB",
            )
        stmt = select(func.count()).select_from(Bond).where(where)
        try:
            with Session(self._engine) as session:
                return int(session.exec(stmt).one())
        except Exception as e:
            self.logger.error("Ошибка при count_bonds: %s", e, exc_info=True)
            raise

    def refresh(self, bonds: List[Bond]) -> bool:
        """Сохраняет список готовых объектов Bond в таблицу bonds (upsert по SECID).

        Не создаёт таблицу — структура управляется Alembic. Вызывает save_bonds.

        Args:
            bonds: Список объектов Bond (результат bond_transformer.transform_batch).

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        data_log = get_data_update_logger()
        try:
            data_log.info(
                "[API /bonds/refresh] Таблица bonds: обновляем данные (upsert по SECID), записей: %s",
                len(bonds),
            )
            self.logger.info("Таблица bonds: обновляем данные, записей: %s", len(bonds))
            result = self.save_bonds(bonds)
            if result:
                data_log.info("[API /bonds/refresh] Данные успешно сохранены в таблицу bonds (база: %s)", self.db_path)
                self.logger.info("Таблица bonds успешно обновлена в базе данных: %s", self.db_path)
            else:
                data_log.warning("[API /bonds/refresh] Сохранение в таблицу bonds завершилось с ошибкой")
                self.logger.warning("Сохранение в таблицу bonds завершилось с ошибкой")
            return result
        except Exception as e:
            data_log.error("[API /bonds/refresh] Ошибка при записи в таблицу bonds: %s", e, exc_info=True)
            self.logger.error("Ошибка при создании/обновлении таблицы bonds: %s", e, exc_info=True)
            return False
