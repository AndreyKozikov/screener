"""Репозиторий для запросов и фильтрации облигаций из базы данных.

Модуль содержит класс BondsRepository для работы с таблицей bonds через
SQLModel API: выборка с фильтрами, подсчёт, пакетное сохранение (upsert).
Все операции выполняются через SQLModel/SQLAlchemy API без текстовых SQL.
"""

import logging
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, and_, text
from sqlmodel import Session, create_engine, select

from db_repository.models.bond import Bond, BondMarketData, BondMarketDataYield, BondSecurity
from db_repository.config.paths import DB_PATH


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

    @staticmethod
    def _not_matured_sql(alias: str = "b") -> str:
        """SQL-фрагмент для text-запросов с параметром active_cutoff_date."""
        return (
            f"({alias}.maturity_date IS NULL "
            f"OR TRIM({alias}.maturity_date) = '' "
            f"OR TRIM({alias}.maturity_date) = '0000-00-00' "
            f"OR TRIM({alias}.maturity_date) > :active_cutoff_date)"
        )

    @staticmethod
    def _active_cutoff_params() -> Dict[str, str]:
        """Параметры для text-запросов, исключающих погашенные бумаги."""
        return {"active_cutoff_date": date.today().isoformat()}

    def _base_bond_conditions(self, *, exclude_spob: bool = False) -> List[Any]:
        """Базовые условия для рабочих выборок облигаций."""
        conditions = [
            self._not_pact_condition(),
            self._not_matured_condition(),
        ]
        if exclude_spob:
            conditions.append(self._not_spob_condition())
        return conditions







    def get_bond_detail_by_secid(
        self, secid: str
    ) -> Optional[
        Tuple[
            Bond,
            Optional[BondSecurity],
            Optional[BondMarketData],
            Optional[BondMarketDataYield],
        ]
    ]:
        """Получает Bond, BondSecurity, BondMarketData и BondMarketDataYield по secid.

        Args:
            secid: Идентификатор ценной бумаги.

        Returns:
            Кортеж (Bond, BondSecurity|None, BondMarketData|None, BondMarketDataYield|None)
            или None, если Bond не найден.
        """
        try:
            with Session(self._engine) as session:
                # Ищем активный Bond по secid, исключая boardid=PACT
                stmt = select(Bond).where(
                    and_(
                        Bond.secid == secid,
                        *self._base_bond_conditions(),
                    )
                )
                bond = session.exec(stmt).first()
                if bond is None:
                    return None
                
                # Получаем связанные записи по bond_id
                bond_id = bond.id
                
                security_stmt = select(BondSecurity).where(BondSecurity.bond_id == bond_id)
                security = session.exec(security_stmt).first()
                
                market_data_stmt = select(BondMarketData).where(BondMarketData.bond_id == bond_id)
                market_data = session.exec(market_data_stmt).first()
                
                market_data_yield_stmt = select(BondMarketDataYield).where(
                    BondMarketDataYield.bond_id == bond_id
                )
                market_data_yield = session.exec(market_data_yield_stmt).first()
                
                return (bond, security, market_data, market_data_yield)
        except Exception as e:
            self.logger.error(
                "Ошибка при получении деталей облигации %s: %s",
                secid,
                e,
                exc_info=True,
            )
            return None

    def get_reg_number_by_secid(self, secid: str) -> Optional[str]:
        """Получает регистрационный номер облигации по SECID из таблицы bondsecurity.

        Args:
            secid: Идентификатор ценной бумаги (SECID).

        Returns:
            Регистрационный номер или None, если не найден.
        """
        stmt = text(f"""
            SELECT bs.reg_number
            FROM bonds b
            JOIN bondsecurity bs ON bs.bond_id = b.id
            WHERE b.secid = :secid 
                AND bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
                AND {self._not_matured_sql("b")}
            LIMIT 1
        """)
        try:
            with Session(self._engine) as session:
                params = {"secid": secid.strip(), **self._active_cutoff_params()}
                row = session.execute(stmt, params).fetchone()
                if row is None:
                    return None
                reg = row[0]
                return str(reg).strip() if reg else None
        except Exception as e:
            self.logger.warning(
                "Ошибка при получении reg_number для secid=%s: %s",
                secid,
                e,
            )
            return None

    def get_emitent_inn_by_secid(self, secid: str) -> Optional[str]:
        """Получает ИНН эмитента по SECID облигации из таблицы emitents.

        Связь: bond.secid -> bond_emitents.emitent_id -> emitents.id -> emitents.inn.

        Args:
            secid: Идентификатор ценной бумаги (SECID).

        Returns:
            ИНН эмитента или None, если эмитент или ИНН отсутствуют.
        """
        stmt = text(f"""
            SELECT e.inn
            FROM bonds b
            JOIN bond_emitents be ON be.secid = b.secid
            JOIN emitents e ON be.emitent_id = e.id
            WHERE b.secid = :secid 
                AND e.inn IS NOT NULL AND trim(e.inn) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
                AND {self._not_matured_sql("b")}
        """)
        try:
            with Session(self._engine) as session:
                params = {"secid": secid, **self._active_cutoff_params()}
                row = session.execute(stmt, params).fetchone()
                if row is None:
                    return None
                inn = row[0]
                return str(inn).strip() if inn else None
        except Exception as e:
            self.logger.warning(
                "Ошибка при получении ИНН эмитента для secid=%s: %s",
                secid,
                e,
            )
            return None

    def get_id_secid_list(self) -> List[Tuple[int, str]]:
        """Возвращает список пар (id, secid) для всех облигаций одним запросом.

        Используется при обновлении купонов: одна выборка для построения
        маппинга secid → id и итерации по облигациям без дополнительных
        запросов к БД.

        Returns:
            Список кортежей (bond_id, secid). Пустой список при ошибке или
            отсутствии записей.
        """
        stmt = select(Bond.id, Bond.secid).where(and_(*self._base_bond_conditions()))
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                return [(int(r.id), str(r.secid)) for r in rows]
        except Exception as e:
            self.logger.error("Ошибка при get_id_secid_list: %s", e, exc_info=True)
            return []

    def get_bond_id_by_secid(self, secid: str) -> Optional[int]:
        """Возвращает bond_id (id в таблице bonds) по SECID облигации.

        Args:
            secid: Идентификатор облигации (SECID).

        Returns:
            Id записи в таблице bonds или None, если облигация не найдена.
        """
        if not secid or not str(secid).strip():
            return None
        stmt = select(Bond.id).where(
            and_(
                Bond.secid == secid.strip(),
                *self._base_bond_conditions(),
            )
        )
        try:
            with Session(self._engine) as session:
                row = session.exec(stmt).first()
                return int(row) if row is not None else None
        except Exception as e:
            self.logger.error("Ошибка при get_bond_id_by_secid(%s): %s", secid, e, exc_info=True)
            return None

    def get_secids_by_ids(self, bond_ids: List[int]) -> List[str]:
        """Возвращает список SECID для указанных bond_id.

        Args:
            bond_ids: Список первичных ключей из таблицы bonds.

        Returns:
            Список SECID (непустых). Пустой список при ошибке или пустом вводе.
        """
        if not bond_ids:
            return []
        stmt = select(Bond.secid).where(
            and_(
                Bond.id.in_(bond_ids),
                *self._base_bond_conditions(),
            )
        )
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                return [str(r).strip() for r in rows if r and str(r).strip()]
        except Exception as e:
            self.logger.error(
                "Ошибка при get_secids_by_ids: %s", e, exc_info=True
            )
            return []

    def get_all_secids(self) -> List[str]:
        """Return the sorted unique SECIDs used for history refreshes."""
        stmt = select(Bond.secid).where(and_(*self._base_bond_conditions()))
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                return sorted({str(row).strip() for row in rows if row and str(row).strip()})
        except Exception as exc:
            self.logger.error("Ошибка при get_all_secids: %s", exc, exc_info=True)
            return []


    def get_bonds_for_ratings_pipeline(
        self,
    ) -> List[Tuple[int, str, Optional[int]]]:
        """Возвращает список облигаций для пайплайна рейтингов.

        Извлекает id, secid и moex_emitent_id (emitents.moex_id) для каждой
        облигации. Пропускает записи без secid.

        Returns:
            Список кортежей (bond_id, secid, moex_emitent_id).
            moex_emitent_id — MOEX ID эмитента (EMITTER_ID) или None.
        """
        stmt = text(f"""
            SELECT b.id, b.secid, e.moex_id
            FROM bonds b
            LEFT JOIN bond_emitents be ON be.secid = b.secid
            LEFT JOIN emitents e ON e.id = be.emitent_id
            WHERE b.secid IS NOT NULL AND TRIM(b.secid) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
                AND {self._not_matured_sql("b")}
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt, self._active_cutoff_params()).fetchall()
            return [
                (int(r[0]), str(r[1]).strip(), int(r[2]) if r[2] is not None else None)
                for r in rows
            ]
        except Exception as e:
            self.logger.error(
                "Ошибка при get_bonds_for_ratings_pipeline: %s", e, exc_info=True
            )
            return []

    def get_floater_secids(self, rating: Optional[str] = None) -> List[str]:
        """Возвращает список SECID корпоративных облигаций вида «флоатер» (bond_kind = 8).

        Исключает ОФЗ (bond_type = 2), муниципальные (bond_type = 4)
        и субфедеральные (bond_type = 5) бумаги — только корпоративные выпуски.

        Args:
            rating: Если указан — возвращаются только флоатеры с данным рейтингом
                (сравнение без учёта регистра и пробелов). None — все флоатеры.

        Returns:
            Список SECID флоатеров. Пустой список при ошибке или отсутствии записей.
        """
        _EXCLUDED_BOND_TYPES: tuple[int, ...] = (2, 4, 5)
        conditions: List[Any] = [
            Bond.bond_kind == 6,
            Bond.bond_type.isnot(None),
            Bond.bond_type.notin_(_EXCLUDED_BOND_TYPES),
            *self._base_bond_conditions(),
        ]
        if rating is not None and rating.strip():
            conditions.append(
                func.upper(func.trim(Bond.rating)) == rating.strip().upper()
            )
        stmt = select(Bond.secid).where(and_(*conditions))
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                return [str(r) for r in rows if r]
        except Exception as e:
            self.logger.error("Ошибка при получении списка флоатеров: %s", e, exc_info=True)
            return []





    def get_secids_by_regnumber(self, regnumber: str) -> List[str]:
        """Returns list of SECIDs for bonds with the given registration number.

        Looks up through bondsecurity.reg_number → bonds.secid.

        Args:
            regnumber: Registration number of the bond.

        Returns:
            List of SECIDs matching the registration number. Empty list if none found.
        """
        if not regnumber or not str(regnumber).strip():
            return []
        stmt = text(f"""
            SELECT DISTINCT b.secid
            FROM bonds b
            JOIN bondsecurity bs ON bs.bond_id = b.id
            WHERE TRIM(bs.reg_number) = :regnumber
                AND b.secid IS NOT NULL AND TRIM(b.secid) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
                AND {self._not_matured_sql("b")}
        """)
        try:
            with Session(self._engine) as session:
                params = {
                    "regnumber": regnumber.strip(),
                    **self._active_cutoff_params(),
                }
                rows = session.execute(
                    stmt, params
                ).fetchall()
                return [str(r[0]).strip() for r in rows if r[0]]
        except Exception as e:
            self.logger.error(
                "Error in get_secids_by_regnumber(%s): %s",
                regnumber, e, exc_info=True,
            )
            return []

