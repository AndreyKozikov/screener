from typing import Optional, List, Any, Dict, Sequence
from db_repository.core.database_init import get_session
from db_repository.models.bond_filters import BondFilters
from sqlmodel import select, Session
from db_repository.models.bond import Bond
from db_repository.models.coupon import Coupon
from sqlalchemy import (delete, func, or_, and_, case, update, text)
from sqlalchemy.orm import selectinload, joinedload
from datetime import date
from db_repository.config.constants import RATINGS_ORDER
from sqlalchemy import func
from db_repository.models.bond import (Bond, BondSecurity, BondMarketData, BondMarketDataYield)


class BondRepository:

    _RELATED_TABLES: List[Dict[str, Any]] = [
        {
            "temp_table": "tmp_bondsecurity",
            "target_table": "bondsecurity",
            "model": BondSecurity,
            "data_key": "securities",
        },
        {
            "temp_table": "tmp_bondmarketdata",
            "target_table": "bondmarketdata",
            "model": BondMarketData,
            "data_key": "marketdata",
        },
        {
            "temp_table": "tmp_bondmarketdatayield",
            "target_table": "bondmarketdatayield",
            "model": BondMarketDataYield,
            "data_key": "marketdata_yields",
        },
    ]

    def __init__(self):
        pass

    @staticmethod
    def _not_pact_condition() -> Any:
        """Исключает режим PACT из рабочих выборок."""
        return or_(
            Bond.boardid.is_(None),
            func.upper(func.trim(Bond.boardid)) != "PACT",
        )

    @staticmethod
    def _not_spob_condition() -> Any:
        """Исключает режим SPOB из рабочих выборок."""
        return or_(
            Bond.boardid.is_(None),
            func.upper(func.trim(Bond.boardid)) != "SPOB",
        )

    @staticmethod
    def _not_matured_condition(reference_date: Optional[date] = None) -> Any:
        """Исключает облигации с датой погашения сегодня или раньше."""
        cutoff = (reference_date or date.today()).isoformat()
        maturity = func.trim(Bond.maturity_date)
        return or_(
            Bond.maturity_date.is_(None),
            maturity == "",
            maturity == "0000-00-00",
            maturity > cutoff,
        )

    def _base_bond_conditions(self, *, exclude_spob: bool = False) -> List[Any]:
        """Базовые условия для рабочих выборок облигаций."""
        conditions = [
            self._not_pact_condition(),
            self._not_matured_condition(),
        ]
        if exclude_spob:
            conditions.append(self._not_spob_condition())
        return conditions

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
        return RATINGS_ORDER[low: high + 1]

    def _build_where_conditions(
            self,
            filters: BondFilters,
            exclude_spob: bool = False,
    ) -> Any:
        """Формирует комбинированное условие WHERE для запросов к Bond.

        Returns:
            Выражение SQLAlchemy (and_ из условий) или True (1=1).
        """
        conditions: List[Any] = self._base_bond_conditions(exclude_spob=exclude_spob)
        if filters.coupon_min is not None:
            conditions.append(Bond.coupon_percent >= filters.coupon_min)
        if filters.coupon_max is not None:
            conditions.append(Bond.coupon_percent <= filters.coupon_max)
        if filters.yield_min is not None:
            conditions.append(Bond.yield_to_maturity >= filters.yield_min)
        if filters.yield_max is not None:
            conditions.append(Bond.yield_to_maturity <= filters.yield_max)
        if filters.coupon_yield_min is not None:
            conditions.append(Bond.coupon_yield_to_price >= filters.coupon_yield_min)
        if filters.coupon_yield_max is not None:
            conditions.append(Bond.coupon_yield_to_price <= filters.coupon_yield_max)
        if filters.matdate_from is not None:
            conditions.append(Bond.maturity_date >= filters.matdate_from.isoformat())
        if filters.matdate_to is not None:
            conditions.append(Bond.maturity_date <= filters.matdate_to.isoformat())
        if filters.listlevel:
            conditions.append(Bond.listing_level.in_(filters.listlevel))
        if filters.faceunit:
            conditions.append(Bond.face_unit.in_(filters.faceunit))
        if filters.bondtype:
            conditions.append(Bond.bond_type.in_(filters.bondtype))
        if filters.bondtype43:
            conditions.append(Bond.bond_kind.in_(filters.bondtype43))
        ratings_in_range = self._rating_range_list(filters.rating_min, filters.rating_max)
        if ratings_in_range:
            conditions.append(Bond.rating.isnot(None))
            conditions.append(Bond.rating != "")
            conditions.append(func.upper(func.trim(Bond.rating)).in_([r.upper() for r in ratings_in_range]))
        return and_(*conditions)

    def select(
            self,
            filters: BondFilters,
            exclude_spob: bool = False,
    ):
        """Выборка облигаций с динамическими фильтрами через SQLModel API.

        Условия формируются через _build_where_conditions; запрос выполняется
        через select(Bond).where(...). Возвращает список объектов Bond.

        Args:
            filters: Объект BondFilters.

        Returns:
            Список объектов Bond, удовлетворяющих фильтрам.

        Raises:
            Exception: При ошибке работы с БД.
        """
        where = self._build_where_conditions(
            filters=filters,
            exclude_spob=exclude_spob,
        )

        try:
            with get_session() as session:
                stmt = select(Bond).where(where)
                bonds = session.exec(stmt).all()
                bond_ids = [bond.id for bond in bonds]
                subquery = (
                    select(
                        Coupon.bond_id,
                        func.min(Coupon.coupondate).label("coupondate")
                    )
                    .where(
                        Coupon.bond_id.in_(bond_ids),
                        Coupon.coupondate >= date.today()
                    )
                    .group_by(Coupon.bond_id)
                    .subquery()
                )

                stmt = (
                    select(Coupon)
                    .join(
                        subquery,
                        (Coupon.bond_id == subquery.columns.bond_id)
                        & (Coupon.coupondate == subquery.columns.coupondate)
                    )
                )

                next_coupons = session.exec(stmt).all()

            # self.logger.debug("Выбрано %s записей из таблицы bonds с применением фильтров", len(result))
            return bonds, next_coupons
        except Exception as e:
            # self.logger.error("Ошибка при select: %s", e, exc_info=True)
            raise

    async def bond_details(self, secid):
        try:
            with (get_session() as session):
                stmt = (
                    select(Bond)
                    .options(
                    selectinload(Bond.coupons),
                    joinedload(Bond.security),
                    joinedload(Bond.marketdata),
                    joinedload(Bond.marketdata_yields),
                    )
                    .where(Bond.secid == secid)
                )
                bond = session.exec(stmt).first()
        except Exception as e:
            raise
        return bond

    def get_all_bond_with_details(self):
        stmt = (
            select(Bond)
            .options(
                selectinload(Bond.security),
                selectinload(Bond.marketdata),
                selectinload(Bond.marketdata_yields),
            )
        )
        with get_session() as session:
            result = session.exec(stmt).all()
        return result


    def count(
            self,
            filters: BondFilters,
            exclude_spob: bool = False
    ) -> int:
        """Подсчёт облигаций с теми же фильтрами, что и select.

        Returns:
            Количество записей Bond, удовлетворяющих условиям.
        """

        where = self._build_where_conditions(
            filters=filters,
            exclude_spob=exclude_spob,
        )
        stmt = select(func.count()).select_from(Bond).where(where)
        try:
            with get_session() as session:
                return int(session.exec(stmt).one())
        except Exception as e:
            raise
            # self.logger.error("Ошибка при count: %s", e, exc_info=True)

    def count_bonds(
            self,
            exclude_spob: bool = False,
    ) -> int:
        """Возвращает общее количество облигаций в таблице bonds (без фильтров по рейтингу и др.).

        Используется для поля total в ответе API.

        Args:
            exclude_spob: Исключить облигации с режимом торгов SPOB.

        Returns:
            Количество записей в таблице bonds.
        """
        conditions: List[Any] = self._base_bond_conditions(exclude_spob=exclude_spob)
        where = and_(*conditions) if conditions else True
        stmt = select(func.count()).select_from(Bond).where(where)
        try:
            with get_session() as session:
                return int(session.exec(stmt).one())
        except Exception as e:
            raise
            # self.logger.error("Ошибка при count_bonds: %s", e, exc_info=True)

    async def get_bondid_by_secid(
            self,
            secid: List[str],
    ):
        stmt = (
            select(Bond.secid, Bond.id)
            .where(Bond.secid.in_(secid))
        )
        try:
            with get_session() as session:
                result = session.exec(stmt).all()
                return result
        except Exception as e:
            raise

    async def get_all_secids(self):
        stmt = (
            select(Bond.secid)
        )
        try:
            with get_session() as session:
                result = session.exec(stmt).all()
                return result
        except Exception as e:
            raise

    def bonds_data_update(self, data: dict[str, list[dict[str, Any]]]):
        with get_session() as session:

            self._create_temp_tables(session)
            self._insert_all_temp_data(session, data)
            self._upsert_bonds(session)

            for cfg in self._RELATED_TABLES:
                self._upsert_related(
                    session,
                    temp_table=cfg["temp_table"],
                    target_table=cfg["target_table"],
                    model=cfg["model"]
                )
            session.commit()

    def _create_temp_tables(
            self,
            session: Session
    ):
        session.exec(text(
           "CREATE TEMP TABLE tmp_bonds AS "
           "SELECT * FROM bonds WHERE 0"
        ))

        for cfg in self._RELATED_TABLES:
            session.exec(text(
                f"CREATE TEMP TABLE {cfg["temp_table"]} AS "
                f"SELECT * FROM {cfg["target_table"]} WHERE 0"
            ))

            session.exec(text(
                f"ALTER TABLE {cfg["temp_table"]} ADD COLUMN secid TEXT"
            ))

    def _insert_temp_data(
            self,
            session: Session,
            data: dict[str, list[dict[str, Any]]],
    ) -> None:

        self._bulk_insert(session, "tmp_bonds", data["bonds"])
        for cfg in self._RELATED_TABLES:
            self._bulk_insert(
                session,
                cfg["temp_table"],
                data[cfg["data_key"]],
            )

    @staticmethod
    def _bulk_insert(
            session: Session,
            table_name: str,
            rows: list[dict[str, Any]],
    ) -> None:

        if not rows:
            return

        columns: Sequence[str] = list(rows[0].keys())

        column_names = ", ".join(
            f'"{column}"'
            for column in columns
        )

        placeholders = ", ".join(
            f":{column}"
            for column in columns
        )

        session.exec(
            text(f"""
                    INSERT INTO "{table_name}"
                    ({column_names})
                    VALUES ({placeholders})
                """),
            rows,
        )

    def _upsert_bonds(
        self,
        session: Session,
    ) -> None:

        columns = [
            column.name
            for column in Bond.__table__.columns
            if column.name != "id"
        ]

        column_names = ", ".join(columns)

        update_values = ", ".join(
            f"{column} = excluded.{column}"
            for column in columns
            if column not in {"secid", "boardid"}
        )

        session.exec(
            text(f"""
                INSERT INTO bonds ({column_names})
                SELECT {column_names}
                FROM tmp_bonds
                ON CONFLICT (secid, boardid)
                DO UPDATE SET{update_values}
            """)
        )

    def _upsert_related(
        self,
        session: Session,
        temp_table: str,
        target_table: str,
        model: Any,
    ) -> None:

        columns = [
            column.name
            for column in model.__table__.columns
            if column.name not in {"id", "bond_id"}
        ]

        target_columns = ", ".join(["bond_id", *columns])
        select_columns = ", ".join(["b.id",*(f"t.{column}" for column in columns)])
        update_values = ", ".join(f"{column} = excluded.{column}" for column in columns)

        session.exec(
            text(f"""
                INSERT INTO {target_table} ({target_columns})
                SELECT {select_columns}
                FROM {temp_table} AS t
                JOIN bonds AS b
                  ON b.secid = t.secid
                 AND b.boardid = t.boardid

                ON CONFLICT (bond_id)
                DO UPDATE SET
                    {update_values}
            """)
        )

db_repository: Optional[BondRepository] = None


def get_db_repository():
    global db_repository
    if db_repository is None:
        db_repository = BondRepository()
    return db_repository
