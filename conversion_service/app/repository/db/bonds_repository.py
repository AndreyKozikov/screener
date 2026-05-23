"""Репозиторий для запросов и фильтрации облигаций из базы данных.

Модуль содержит класс BondsRepository для работы с таблицей bonds через
SQLModel API: выборка с фильтрами, подсчёт, пакетное сохранение (upsert).
Все операции выполняются через SQLModel/SQLAlchemy API без текстовых SQL.
"""

import logging
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, or_, and_, text
from sqlmodel import Session, create_engine, select

from app.models import Bond, BondFilters, BondMarketData, BondMarketDataYield, BondSecurity
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

    @staticmethod
    def _to_sql_date(val: Any) -> Optional[str]:
        """Конвертирует date в строку YYYY-MM-DD для SQLite."""
        if val is None:
            return None
        if isinstance(val, date):
            return val.strftime("%Y-%m-%d")
        return str(val) if val else None

    def save_bonds(self, bonds: List[Bond]) -> bool:
        """Upsert облигаций: INSERT ... ON CONFLICT(secid, boardid) DO UPDATE.

        Не выполняет DELETE. При конфликте по (secid, boardid) обновляет
        рыночные данные, не затрагивая id. Сохраняет стабильность id.
        Исключает облигации с boardid=PACT из сохранения.

        Args:
            bonds: Список объектов Bond для вставки/обновления.

        Returns:
            True при успехе, False при ошибке или отсутствии данных.
        """
        if not bonds:
            self.logger.warning("Нет данных для вставки")
            return False
        
        # Фильтруем облигации с boardid=PACT перед сохранением
        filtered_bonds = [
            bond for bond in bonds
            if bond.boardid is None or str(bond.boardid).strip().upper() != "PACT"
        ]
        
        if not filtered_bonds:
            self.logger.warning("Нет данных для вставки после фильтрации boardid=PACT")
            return False
        
        excluded_count = len(bonds) - len(filtered_bonds)
        if excluded_count > 0:
            self.logger.info(
                "Исключено %s облигаций с boardid=PACT из сохранения (всего: %s, отфильтровано: %s)",
                excluded_count,
                len(bonds),
                len(filtered_bonds)
            )
        
        data_log = get_data_update_logger()
        try:
            stmt = text("""
                INSERT INTO bonds (
                    secid, boardid, isin, name, secname, rating, rating_agency,
                    current_price, coupon_yield_to_price, yield_to_maturity, face_value,
                    currency, face_unit, coupon_value, coupon_percent, coupon_frequency,
                    coupon_period, accrued_interest, duration_years, duration, duration_waprice,
                    has_put_option, has_call_option, maturity_date, listing_level,
                    bond_type, bond_kind, offer_date, status, trading_status, next_coupon,
                    board_name, call_option_date, put_option_date, emitent_id
                ) VALUES (
                    :secid, :boardid, :isin, :name, :secname, :rating, :rating_agency,
                    :current_price, :coupon_yield_to_price, :yield_to_maturity, :face_value,
                    :currency, :face_unit, :coupon_value, :coupon_percent, :coupon_frequency,
                    :coupon_period, :accrued_interest, :duration_years, :duration, :duration_waprice,
                    :has_put_option, :has_call_option, :maturity_date, :listing_level,
                    :bond_type, :bond_kind, :offer_date, :status, :trading_status, :next_coupon,
                    :board_name, :call_option_date, :put_option_date, :emitent_id
                )
                ON CONFLICT(secid, boardid) DO UPDATE SET
                    isin=excluded.isin, name=excluded.name, secname=excluded.secname,
                    rating=CASE WHEN excluded.rating IS NOT NULL AND trim(coalesce(excluded.rating, '')) != '' THEN excluded.rating ELSE bonds.rating END,
                    rating_agency=CASE WHEN excluded.rating_agency IS NOT NULL AND trim(coalesce(excluded.rating_agency, '')) != '' THEN excluded.rating_agency ELSE bonds.rating_agency END,
                    current_price=excluded.current_price,
                    coupon_yield_to_price=excluded.coupon_yield_to_price,
                    yield_to_maturity=excluded.yield_to_maturity,
                    face_value=excluded.face_value, currency=excluded.currency,
                    face_unit=excluded.face_unit, coupon_value=excluded.coupon_value,
                    coupon_percent=excluded.coupon_percent,
                    coupon_frequency=excluded.coupon_frequency,
                    coupon_period=excluded.coupon_period,
                    accrued_interest=excluded.accrued_interest,
                    duration_years=excluded.duration_years,
                    duration=excluded.duration,
                    duration_waprice=excluded.duration_waprice,
                    has_put_option=excluded.has_put_option,
                    has_call_option=excluded.has_call_option,
                    maturity_date=excluded.maturity_date,
                    listing_level=excluded.listing_level,
                    bond_type=excluded.bond_type, bond_kind=excluded.bond_kind,
                    offer_date=excluded.offer_date, status=excluded.status,
                    trading_status=excluded.trading_status, next_coupon=excluded.next_coupon,
                    board_name=excluded.board_name,
                    call_option_date=excluded.call_option_date,
                    put_option_date=excluded.put_option_date
            """)
            with Session(self._engine) as session:
                for bond in filtered_bonds:
                    params = {
                        "secid": bond.secid,
                        "boardid": bond.boardid,
                        "isin": bond.isin,
                        "name": bond.name,
                        "secname": bond.secname,
                        "rating": bond.rating,
                        "rating_agency": bond.rating_agency,
                        "current_price": bond.current_price,
                        "coupon_yield_to_price": bond.coupon_yield_to_price,
                        "yield_to_maturity": bond.yield_to_maturity,
                        "face_value": bond.face_value,
                        "currency": bond.currency,
                        "face_unit": bond.face_unit,
                        "coupon_value": bond.coupon_value,
                        "coupon_percent": bond.coupon_percent,
                        "coupon_frequency": bond.coupon_frequency,
                        "coupon_period": bond.coupon_period,
                        "accrued_interest": bond.accrued_interest,
                        "duration_years": bond.duration_years,
                        "duration": bond.duration,
                        "duration_waprice": bond.duration_waprice,
                        "has_put_option": bond.has_put_option,
                        "has_call_option": bond.has_call_option,
                        "maturity_date": bond.maturity_date,
                        "listing_level": bond.listing_level,
                        "bond_type": bond.bond_type,
                        "bond_kind": bond.bond_kind,
                        "offer_date": bond.offer_date,
                        "status": bond.status,
                        "trading_status": bond.trading_status,
                        "next_coupon": bond.next_coupon,
                        "board_name": bond.board_name,
                        "call_option_date": bond.call_option_date,
                        "put_option_date": bond.put_option_date,
                        "emitent_id": bond.emitent_id,
                    }
                    session.execute(stmt, params)
                session.commit()
            data_log.info(
                "[API /bonds/refresh] В таблицу bonds записано записей: %s (база: %s)",
                len(filtered_bonds),
                self.db_path,
            )
            self.logger.info("Успешно вставлено %s записей в таблицу bonds", len(filtered_bonds))
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
        # Всегда исключаем облигации с boardid=PACT
        conditions.append(
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            )
        )
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
            conditions.append(Bond.face_unit.in_(currency))
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
            bond_type_ids = filters.bondtype
            bond_kind_ids = filters.bondtype43

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
            bond_type_ids = filters.bondtype
            bond_kind_ids = filters.bondtype43

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
        conditions: List[Any] = []
        # Всегда исключаем облигации с boardid=PACT
        conditions.append(
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            )
        )
        if exclude_spob:
            conditions.append(
                or_(
                    Bond.boardid.is_(None),
                    func.upper(func.trim(Bond.boardid)) != "SPOB",
                )
            )
        where = and_(*conditions) if conditions else True
        stmt = select(func.count()).select_from(Bond).where(where)
        try:
            with Session(self._engine) as session:
                return int(session.exec(stmt).one())
        except Exception as e:
            self.logger.error("Ошибка при count_bonds: %s", e, exc_info=True)
            raise

    def save_bond_securities(
        self, securities: List[Dict[str, Any]]
    ) -> bool:
        """Удаляет все записи из bondsecurity и вставляет новые. bond_id — через подзапрос.

        Args:
            securities: Список словарей с secid, boardid и полями BondSecurity.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not securities:
            self.logger.debug("Нет данных BondSecurity для вставки")
            return True
        data_log = get_data_update_logger()
        stmt = text("""
            INSERT INTO bondsecurity (
                bond_id, boardid, prev_waprice, yield_at_prev_waprice, prev_price,
                lot_size, reg_number, decimals, issue_size, prev_legal_close_price,
                prev_date, remarks, market_code, instr_id, sector_id, min_step,
                face_unit, buyback_price, buyback_date, lat_name, issue_size_placed,
                sec_type, settle_date, lot_value, face_value_on_settle_date,
                date_yield_from_issuer
            )
            SELECT
                (SELECT id FROM bonds WHERE secid = :secid AND (
                    (boardid IS NULL AND :boardid IS NULL) OR (boardid = :boardid)
                ) LIMIT 1),
                :boardid, :prev_waprice, :yield_at_prev_waprice, :prev_price,
                :lot_size, :reg_number, :decimals, :issue_size, :prev_legal_close_price,
                :prev_date, :remarks, :market_code, :instr_id, :sector_id, :min_step,
                :face_unit, :buyback_price, :buyback_date, :lat_name, :issue_size_placed,
                :sec_type, :settle_date, :lot_value, :face_value_on_settle_date,
                :date_yield_from_issuer
        """)
        try:
            with Session(self._engine) as session:
                session.execute(delete(BondSecurity))
                session.commit()
                for rec in securities:
                    params = {
                        "secid": rec["secid"],
                        "boardid": rec["boardid"],
                        "prev_waprice": rec.get("prev_waprice"),
                        "yield_at_prev_waprice": rec.get("yield_at_prev_waprice"),
                        "prev_price": rec.get("prev_price"),
                        "lot_size": rec.get("lot_size"),
                        "reg_number": rec.get("reg_number"),
                        "decimals": rec.get("decimals"),
                        "issue_size": rec.get("issue_size"),
                        "prev_legal_close_price": rec.get("prev_legal_close_price"),
                        "prev_date": self._to_sql_date(rec.get("prev_date")),
                        "remarks": rec.get("remarks"),
                        "market_code": rec.get("market_code"),
                        "instr_id": rec.get("instr_id"),
                        "sector_id": rec.get("sector_id"),
                        "min_step": rec.get("min_step"),
                        "face_unit": rec.get("face_unit"),
                        "buyback_price": rec.get("buyback_price"),
                        "buyback_date": self._to_sql_date(rec.get("buyback_date")),
                        "lat_name": rec.get("lat_name"),
                        "issue_size_placed": rec.get("issue_size_placed"),
                        "sec_type": rec.get("sec_type"),
                        "settle_date": self._to_sql_date(rec.get("settle_date")),
                        "lot_value": rec.get("lot_value"),
                        "face_value_on_settle_date": rec.get("face_value_on_settle_date"),
                        "date_yield_from_issuer": self._to_sql_date(rec.get("date_yield_from_issuer")),
                    }
                    session.execute(stmt, params)
                session.commit()
            data_log.info(
                "[API /bonds/refresh] В таблицу bondsecurity записано: %s записей",
                len(securities),
            )
            self.logger.info(
                "Успешно вставлено %s записей в таблицу bondsecurity",
                len(securities),
            )
            return True
        except Exception as e:
            data_log.error(
                "[API /bonds/refresh] Ошибка при записи в bondsecurity: %s",
                e,
                exc_info=True,
            )
            self.logger.error("Ошибка при сохранении BondSecurity: %s", e, exc_info=True)
            return False

    def save_bond_market_data(
        self, market_data_list: List[Dict[str, Any]]
    ) -> bool:
        """Удаляет все записи из bondmarketdata и вставляет новые. bond_id — через подзапрос.

        Args:
            market_data_list: Список словарей с secid, boardid и полями BondMarketData.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not market_data_list:
            self.logger.debug("Нет данных BondMarketData для вставки")
            return True
        data_log = get_data_update_logger()
        stmt = text("""
            INSERT INTO bondmarketdata (
                bond_id, boardid, bid, offer, spread, bid_depth, offer_depth,
                open_price, low, high, last_price, last_change, last_change_prcnt,
                qty, value, value_usd, waprice, last_cnt_to_last_waprice,
                wap_to_prev_waprice_prcnt, wap_to_prev_waprice, close_price,
                market_price_today, market_price, last_to_prev_price, num_trades,
                vol_today, val_today, val_today_usd, etf_settle_price, update_time
            )
            SELECT
                (SELECT id FROM bonds WHERE secid = :secid AND (
                    (boardid IS NULL AND :boardid IS NULL) OR (boardid = :boardid)
                ) LIMIT 1),
                :boardid, :bid, :offer, :spread, :bid_depth, :offer_depth,
                :open_price, :low, :high, :last_price, :last_change, :last_change_prcnt,
                :qty, :value, :value_usd, :waprice, :last_cnt_to_last_waprice,
                :wap_to_prev_waprice_prcnt, :wap_to_prev_waprice, :close_price,
                :market_price_today, :market_price, :last_to_prev_price, :num_trades,
                :vol_today, :val_today, :val_today_usd, :etf_settle_price, :update_time
        """)
        try:
            with Session(self._engine) as session:
                session.execute(delete(BondMarketData))
                session.commit()
                for rec in market_data_list:
                    params = {
                        "secid": rec["secid"],
                        "boardid": rec["boardid"],
                        "bid": rec.get("bid"),
                        "offer": rec.get("offer"),
                        "spread": rec.get("spread"),
                        "bid_depth": rec.get("bid_depth"),
                        "offer_depth": rec.get("offer_depth"),
                        "open_price": rec.get("open_price"),
                        "low": rec.get("low"),
                        "high": rec.get("high"),
                        "last_price": rec.get("last_price"),
                        "last_change": rec.get("last_change"),
                        "last_change_prcnt": rec.get("last_change_prcnt"),
                        "qty": rec.get("qty"),
                        "value": rec.get("value"),
                        "value_usd": rec.get("value_usd"),
                        "waprice": rec.get("waprice"),
                        "last_cnt_to_last_waprice": rec.get("last_cnt_to_last_waprice"),
                        "wap_to_prev_waprice_prcnt": rec.get("wap_to_prev_waprice_prcnt"),
                        "wap_to_prev_waprice": rec.get("wap_to_prev_waprice"),
                        "close_price": rec.get("close_price"),
                        "market_price_today": rec.get("market_price_today"),
                        "market_price": rec.get("market_price"),
                        "last_to_prev_price": rec.get("last_to_prev_price"),
                        "num_trades": rec.get("num_trades"),
                        "vol_today": rec.get("vol_today"),
                        "val_today": rec.get("val_today"),
                        "val_today_usd": rec.get("val_today_usd"),
                        "etf_settle_price": rec.get("etf_settle_price"),
                        "update_time": rec.get("update_time"),
                    }
                    session.execute(stmt, params)
                session.commit()
            data_log.info(
                "[API /bonds/refresh] В таблицу bondmarketdata записано: %s записей",
                len(market_data_list),
            )
            self.logger.info(
                "Успешно вставлено %s записей в таблицу bondmarketdata",
                len(market_data_list),
            )
            return True
        except Exception as e:
            data_log.error(
                "[API /bonds/refresh] Ошибка при записи в bondmarketdata: %s",
                e,
                exc_info=True,
            )
            self.logger.error(
                "Ошибка при сохранении BondMarketData: %s", e, exc_info=True
            )
            return False

    def save_bond_market_data_yields(
        self, yields_list: List[Dict[str, Any]]
    ) -> bool:
        """Удаляет все записи из bondmarketdatayield и вставляет новые. bond_id — через подзапрос.

        Args:
            yields_list: Список словарей с secid, boardid и полями BondMarketDataYield.

        Returns:
            True при успешном сохранении, False при ошибке.
        """
        if not yields_list:
            self.logger.debug("Нет данных BondMarketDataYield для вставки")
            return True
        data_log = get_data_update_logger()
        stmt = text("""
            INSERT INTO bondmarketdatayield (
                bond_id, boardid, price, yield_date, zcyc_moment, yield_date_type,
                effective_yield, duration, zspread_bp, gspread_bp, waprice,
                effective_yield_waprice, duration_waprice, ir, icpi, bei, cbr,
                yield_to_offer, yield_last_coupon, trade_moment, seqnum, systime
            )
            SELECT
                (SELECT id FROM bonds WHERE secid = :secid AND (
                    (boardid IS NULL AND :boardid IS NULL) OR (boardid = :boardid)
                ) LIMIT 1),
                :boardid, :price, :yield_date, :zcyc_moment, :yield_date_type,
                :effective_yield, :duration, :zspread_bp, :gspread_bp, :waprice,
                :effective_yield_waprice, :duration_waprice, :ir, :icpi, :bei, :cbr,
                :yield_to_offer, :yield_last_coupon, :trade_moment, :seqnum, :systime
        """)
        try:
            with Session(self._engine) as session:
                session.execute(delete(BondMarketDataYield))
                session.commit()
                for rec in yields_list:
                    params = {
                        "secid": rec["secid"],
                        "boardid": rec["boardid"],
                        "price": rec.get("price"),
                        "yield_date": rec.get("yield_date"),
                        "zcyc_moment": rec.get("zcyc_moment"),
                        "yield_date_type": rec.get("yield_date_type"),
                        "effective_yield": rec.get("effective_yield"),
                        "duration": rec.get("duration"),
                        "zspread_bp": rec.get("zspread_bp"),
                        "gspread_bp": rec.get("gspread_bp"),
                        "waprice": rec.get("waprice"),
                        "effective_yield_waprice": rec.get("effective_yield_waprice"),
                        "duration_waprice": rec.get("duration_waprice"),
                        "ir": rec.get("ir"),
                        "icpi": rec.get("icpi"),
                        "bei": rec.get("bei"),
                        "cbr": rec.get("cbr"),
                        "yield_to_offer": rec.get("yield_to_offer"),
                        "yield_last_coupon": rec.get("yield_last_coupon"),
                        "trade_moment": rec.get("trade_moment"),
                        "seqnum": rec.get("seqnum"),
                        "systime": rec.get("systime"),
                    }
                    session.execute(stmt, params)
                session.commit()
            data_log.info(
                "[API /bonds/refresh] В таблицу bondmarketdatayield записано: %s записей",
                len(yields_list),
            )
            self.logger.info(
                "Успешно вставлено %s записей в таблицу bondmarketdatayield",
                len(yields_list),
            )
            return True
        except Exception as e:
            data_log.error(
                "[API /bonds/refresh] Ошибка при записи в bondmarketdatayield: %s",
                e,
                exc_info=True,
            )
            self.logger.error(
                "Ошибка при сохранении BondMarketDataYield: %s", e, exc_info=True
            )
            return False

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
                # Ищем Bond по secid, исключая boardid=PACT
                stmt = select(Bond).where(
                    and_(
                        Bond.secid == secid,
                        or_(
                            Bond.boardid.is_(None),
                            func.upper(func.trim(Bond.boardid)) != "PACT",
                        )
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
        stmt = text("""
            SELECT bs.reg_number
            FROM bonds b
            JOIN bondsecurity bs ON bs.bond_id = b.id
            WHERE b.secid = :secid 
                AND bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
            LIMIT 1
        """)
        try:
            with Session(self._engine) as session:
                row = session.execute(stmt, {"secid": secid.strip()}).fetchone()
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

        Связь: bond.emitent_id -> emitents.id, emitents.inn.

        Args:
            secid: Идентификатор ценной бумаги (SECID).

        Returns:
            ИНН эмитента или None, если эмитент или ИНН отсутствуют.
        """
        stmt = text("""
            SELECT e.inn
            FROM bonds b
            JOIN emitents e ON b.emitent_id = e.id
            WHERE b.secid = :secid 
                AND e.inn IS NOT NULL AND trim(e.inn) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
        """)
        try:
            with Session(self._engine) as session:
                row = session.execute(stmt, {"secid": secid}).fetchone()
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

    def update_emitent_ids(self, secid_to_emitent_id: Dict[str, int]) -> int:
        """Обновляет поле emitent_id в таблице bonds по маппингу secid -> emitent_id.

        Вызывается после сохранения эмитентов в БД (пайплайн обновления эмитентов),
        чтобы связать облигации с записью в таблице emitents.

        Args:
            secid_to_emitent_id: Словарь {secid: emitent_id}, где emitent_id — id из emitents.

        Returns:
            Суммарное количество обновлённых строк в таблице bonds.
        """
        if not secid_to_emitent_id:
            return 0
        stmt = text("UPDATE bonds SET emitent_id = :emitent_id WHERE secid = :secid")
        total_updated = 0
        try:
            with Session(self._engine) as session:
                for secid, emitent_id in secid_to_emitent_id.items():
                    result = session.execute(stmt, {"emitent_id": emitent_id, "secid": secid})
                    if result.rowcount is not None:
                        total_updated += result.rowcount
                session.commit()
            self.logger.info(
                "Обновлено emitent_id для %s записей bonds (по %s secid)",
                total_updated,
                len(secid_to_emitent_id),
            )
            return total_updated
        except Exception as e:
            self.logger.error(
                "Ошибка при обновлении emitent_id в bonds: %s", e, exc_info=True
            )
            return 0

    def get_id_secid_list(self) -> List[Tuple[int, str]]:
        """Возвращает список пар (id, secid) для всех облигаций одним запросом.

        Используется при обновлении купонов: одна выборка для построения
        маппинга secid → id и итерации по облигациям без дополнительных
        запросов к БД.

        Returns:
            Список кортежей (bond_id, secid). Пустой список при ошибке или
            отсутствии записей.
        """
        stmt = select(Bond.id, Bond.secid).where(
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            )
        )
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                return [(int(r.id), str(r.secid)) for r in rows]
        except Exception as e:
            self.logger.error("Ошибка при get_id_secid_list: %s", e, exc_info=True)
            return []

    def get_bond_id_by_secid(self, secid: str) -> Optional[int]:
        """Возвращает bond_id (id в таблице bonds) по SECID облигации.

        Используется при сохранении купонов после загрузки из API MOEX для
        одной облигации.

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
                or_(
                    Bond.boardid.is_(None),
                    func.upper(func.trim(Bond.boardid)) != "PACT",
                )
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
            Bond.id.in_(bond_ids),
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            ),
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
        """Возвращает отсортированный список уникальных SECID из таблицы bonds.

        Используется для массовой загрузки истории торгов: один запрос к БД
        вместо чтения bonds.json.

        Returns:
            Отсортированный список уникальных непустых SECID. Пустой список
            при ошибке или отсутствии записей.
        """
        stmt = select(Bond.secid).where(
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            )
        )
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                secids = [str(r).strip() for r in rows if r and str(r).strip()]
                return sorted(set(secids))
        except Exception as e:
            self.logger.error("Ошибка при get_all_secids: %s", e, exc_info=True)
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
        stmt = text("""
            SELECT b.id, b.secid, e.moex_id
            FROM bonds b
            LEFT JOIN emitents e ON e.id = b.emitent_id
            WHERE b.secid IS NOT NULL AND TRIM(b.secid) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt).fetchall()
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
            Bond.bond_kind == 8,
            Bond.bond_type.isnot(None),
            Bond.bond_type.notin_(_EXCLUDED_BOND_TYPES),
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            ),
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

    def get_all_bond_secids(self, rating: Optional[str] = None) -> List[str]:
        """Возвращает список SECID всех облигаций, имеющих регистрационный номер.

        Args:
            rating: Если указан — фильтр по рейтингу.

        Returns:
            Список SECID.
        """
        stmt = select(Bond.secid).join(BondSecurity, BondSecurity.bond_id == Bond.id).where(
            and_(
                BondSecurity.reg_number.isnot(None),
                func.trim(BondSecurity.reg_number) != "",
                or_(
                    Bond.boardid.is_(None),
                    func.upper(func.trim(Bond.boardid)) != "PACT",
                ),
            )
        )
        if rating is not None and rating.strip():
            # Use text condition to match how it's done in other methods if needed, 
            # but here we can use SQLModel.
            stmt = stmt.where(func.upper(func.trim(Bond.rating)) == rating.strip().upper())
            
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                return [str(r) for r in rows if r]
        except Exception as e:
            self.logger.error("Ошибка при получении всех SECID облигаций: %s", e, exc_info=True)
            return []

    def get_secids_without_emitent(self) -> List[str]:
        """Возвращает список SECID облигаций, у которых не проставлен emitent_id.

        Returns:
            Отсортированный список уникальных SECID с пустым emitent_id.
        """
        stmt = select(Bond.secid).where(
            Bond.secid.isnot(None),
            or_(Bond.emitent_id.is_(None), Bond.emitent_id == 0),
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            )
        )
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                secids = [str(r).strip() for r in rows if r and str(r).strip()]
                return sorted(set(secids))
        except Exception as e:
            self.logger.error(
                "Ошибка при get_secids_without_emitent: %s", e, exc_info=True
            )
            return []

    def get_secids_without_rating(self) -> List[str]:
        """Возвращает список SECID облигаций, у которых не проставлен рейтинг.

        Returns:
            Отсортированный список уникальных SECID с пустым rating.
        """
        stmt = select(Bond.secid).where(
            Bond.secid.isnot(None),
            or_(
                Bond.rating.is_(None),
                Bond.rating == "",
                func.trim(Bond.rating) == "",
            ),
            or_(
                Bond.boardid.is_(None),
                func.upper(func.trim(Bond.boardid)) != "PACT",
            )
        )
        try:
            with Session(self._engine) as session:
                rows = session.exec(stmt).all()
                secids = [str(r).strip() for r in rows if r and str(r).strip()]
                return sorted(set(secids))
        except Exception as e:
            self.logger.error(
                "Ошибка при get_secids_without_rating: %s", e, exc_info=True
            )
            return []

    def update_ratings_batch(
        self, secid_to_rating_agency: Dict[str, Tuple[Optional[str], Optional[str]]]
    ) -> int:
        """Обновляет поля rating и rating_agency в bonds по маппингу secid -> (rating, rating_agency).

        Args:
            secid_to_rating_agency: Словарь {secid: (rating, rating_agency)}.

        Returns:
            Суммарное количество обновлённых строк.
        """
        if not secid_to_rating_agency:
            return 0
        stmt = text(
            "UPDATE bonds SET rating = :rating, rating_agency = :rating_agency WHERE secid = :secid"
        )
        total = 0
        try:
            with Session(self._engine) as session:
                for secid, (rating, rating_agency) in secid_to_rating_agency.items():
                    result = session.execute(
                        stmt,
                        {
                            "secid": secid,
                            "rating": rating or None,
                            "rating_agency": rating_agency or None,
                        },
                    )
                    if result.rowcount is not None:
                        total += result.rowcount
                session.commit()
            self.logger.info(
                "Обновлено rating/rating_agency для %s записей bonds (по %s secid)",
                total,
                len(secid_to_rating_agency),
            )
            return total
        except Exception as e:
            self.logger.error(
                "Ошибка при update_ratings_batch: %s", e, exc_info=True
            )
            return 0

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
        stmt = text("""
            SELECT DISTINCT b.secid
            FROM bonds b
            JOIN bondsecurity bs ON bs.bond_id = b.id
            WHERE TRIM(bs.reg_number) = :regnumber
                AND b.secid IS NOT NULL AND TRIM(b.secid) != ''
                AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(
                    stmt, {"regnumber": regnumber.strip()}
                ).fetchall()
                return [str(r[0]).strip() for r in rows if r[0]]
        except Exception as e:
            self.logger.error(
                "Error in get_secids_by_regnumber(%s): %s",
                regnumber, e, exc_info=True,
            )
            return []

    def refresh(self, bonds: List[Bond]) -> bool:
        """Сохраняет список готовых объектов Bond в таблицу bonds (INSERT ON CONFLICT).

        Не создаёт таблицу — структура управляется Alembic. Вызывает save_bonds.
        Не выполняет DELETE; использует upsert для сохранения стабильности id.

        Args:
            bonds: Список объектов Bond (результат bond_transformer.transform_batch).

        Returns:
            True при успехе, False при ошибке.
        """
        data_log = get_data_update_logger()
        try:
            data_log.info(
                "[API /bonds/refresh] Таблица bonds: upsert данных, записей: %s",
                len(bonds),
            )
            self.logger.info("Таблица bonds: обновляем данные, записей: %s", len(bonds))
            ok = self.save_bonds(bonds)
            if ok:
                data_log.info("[API /bonds/refresh] Данные успешно сохранены в таблицу bonds (база: %s)", self.db_path)
                self.logger.info("Таблица bonds успешно обновлена в базе данных: %s", self.db_path)
            else:
                data_log.warning("[API /bonds/refresh] Сохранение в таблицу bonds завершилось с ошибкой или пустой список")
                self.logger.warning("Сохранение в таблицу bonds завершилось с ошибкой или пустой список")
            return ok
        except Exception as e:
            data_log.error("[API /bonds/refresh] Ошибка при записи в таблицу bonds: %s", e, exc_info=True)
            self.logger.error("Ошибка при создании/обновлении таблицы bonds: %s", e, exc_info=True)
            return False
