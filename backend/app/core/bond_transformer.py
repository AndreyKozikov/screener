"""Центральный модуль расчётной логики облигаций.

Содержит класс BondTransformer: загрузка маппингов, объединение payload MOEX
(transform_raw_payload), расчёт доходности, дюрации, рейтингов, флагов оферт
и преобразование сырых данных в объекты Bond для сохранения в БД. Рейтинги
и данные эмитентов загружаются из БД (bond_ratings, emitent_ratings, emitents).
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from app.models import Bond, BondRating, Emitent, EmitentRating, RatingAgency
from app.repository.files.file_storage import FileStorage
from config.paths import (
    BONDS_TYPE_MAPPING_JSON,
    BONDS_TYPE43_MAPPING_JSON,
)
from app.utils.rating_utils import get_rating_index, standardize_rating
from app.services.emitent_service import get_emitent_service


class BondTransformer:
    """Преобразование данных облигаций в формат таблицы БД.

    Загружает маппинги типов и видов облигаций из JSON; рейтинги облигаций
    и данные эмитентов — из БД (bond_ratings, emitent_ratings, rating_agency, emitents).
    Объединяет сырые данные с рейтингами, вычисляет наихудший рейтинг и формирует
    словари для вставки в БД.

    Attributes:
        data_dir: Путь к директории с JSON файлами (маппинги типов/видов).
        storage: Хранилище для чтения JSON.
        session: Сессия SQLModel для запросов к БД (рейтинги, эмитенты).
    """

    def __init__(self, data_dir: Path, storage: FileStorage, db_session: Session):
        """Инициализирует преобразователь данных облигаций.

        Args:
            data_dir: Путь к директории с JSON файлами (маппинги типов/видов).
            storage: Экземпляр FileStorage для чтения JSON.
            db_session: Сессия SQLModel для запросов к таблицам bond_ratings,
                emitent_ratings, rating_agency, emitents, bonds.
        """
        self.data_dir = Path(data_dir)
        self.storage = storage
        self.session = db_session
        self.logger = logging.getLogger(__name__)

    def transform_raw_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Объединяет секции payload (MOEX) по SECID в список словарей облигаций.

        Реализует логику объединения securities, marketdata и marketdata_yields
        по SECID без чтения с диска. Облигации с режимом SPOB исключаются.

        Args:
            payload: Словарь с ключами securities, marketdata, marketdata_yields
                (формат ответа MOEX API).

        Returns:
            Список словарей (по одному на облигацию) с объединёнными полями.
            Готов для передачи в prepare_bonds_for_db.
        """
        bonds_data: List[Dict[str, Any]] = []
        data = payload

        securities = data.get("securities", {})
        sec_columns = securities.get("columns", [])
        sec_data = securities.get("data", [])

        marketdata = data.get("marketdata", {})
        md_columns = marketdata.get("columns", [])
        md_data = marketdata.get("data", [])

        yields_section = data.get("marketdata_yields", {})
        yields_columns = yields_section.get("columns", [])
        yields_data = yields_section.get("data", [])

        marketdata_map: Dict[str, Dict[str, Any]] = {}
        for row in md_data:
            md_dict = dict(zip(md_columns, row))
            secid = md_dict.get("SECID")
            if secid:
                marketdata_map[secid] = md_dict

        yields_map: Dict[str, Dict[str, Any]] = {}
        for row in yields_data:
            y_dict = dict(zip(yields_columns, row))
            secid = y_dict.get("SECID")
            if secid and secid not in yields_map:
                yields_map[secid] = y_dict

        for row in sec_data:
            bond_dict = dict(zip(sec_columns, row))

            boardid = bond_dict.get("BOARDID")
            if boardid and str(boardid).strip().upper() == "SPOB":
                continue

            secid = bond_dict.get("SECID")
            if not secid:
                continue

            if "BONDTYPE" in bond_dict:
                bondtype43_value = bond_dict.get("BONDTYPE")
                if bondtype43_value:
                    bond_dict["BONDTYPE43"] = (
                        bondtype43_value.strip()
                        if isinstance(bondtype43_value, str)
                        else bondtype43_value
                    )

            if secid in marketdata_map:
                bond_dict.update(marketdata_map[secid])
            if secid in yields_map:
                bond_dict.update(yields_map[secid])

            bonds_data.append(bond_dict)

        self.logger.debug("Преобразовано из payload: %s облигаций", len(bonds_data))
        return bonds_data

    def load_mappings(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Загружает маппинги типов и видов облигаций из JSON-файлов.

        Загружает маппинги из bonds_type_mapping.json и bonds_type43_mapping.json
        для преобразования строковых значений типов и видов облигаций в числовые ID.

        Returns:
            Кортеж из двух словарей:
            - type_mapping: Маппинг типов облигаций (строка -> ID).
            - kind_mapping: Маппинг видов облигаций (строка -> ID).
        """
        type_mapping: Dict[str, int] = {}
        kind_mapping: Dict[str, int] = {}

        type_path = self.data_dir / BONDS_TYPE_MAPPING_JSON
        if type_path.exists():
            try:
                data = self.storage.read_json(type_path)
                if isinstance(data, dict):
                    type_mapping = {k: int(v) for k, v in data.items() if v is not None}
                self.logger.debug("Загружен маппинг типов: %s записей", len(type_mapping))
            except Exception as e:
                self.logger.warning("Ошибка при загрузке маппинга типов: %s", e)

        kind_path = self.data_dir / BONDS_TYPE43_MAPPING_JSON
        if kind_path.exists():
            try:
                data = self.storage.read_json(kind_path)
                if isinstance(data, dict):
                    kind_mapping = {k: int(v) for k, v in data.items() if v is not None}
                self.logger.debug("Загружен маппинг видов: %s записей", len(kind_mapping))
            except Exception as e:
                self.logger.warning("Ошибка при загрузке маппинга видов: %s", e)

        return type_mapping, kind_mapping

    def prepare_bonds_for_db(
        self, raw_bonds_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Обогащает сырые данные облигаций рейтингами и эмитентами из БД.

        Рейтинг: сначала из bond_ratings (БД); если не установлен — из emitent_ratings
        по эмитенту облигации (cci_rating_companies). Выполняется стандартизация
        рейтинга и определение наихудшего через _get_worst_rating/standardize_rating/get_rating_index.
        Маппинги загружаются одним запросом с JOIN (без N+1).

        Args:
            raw_bonds_data: Список словарей из API/файла (securities + marketdata + yields).

        Returns:
            Тот же список с добавленными RATINGS, RATING_AGENCY, RATING_LEVEL, BONDTYPE;
            готов для transform_batch.
        """
        ratings_map = self._load_ratings_map()
        emitent_map = self._load_emitent_map()

        for bond in raw_bonds_data:
            secid = bond.get("SECID")
            if not secid:
                continue
            # 1) Рейтинг: сначала из bond_ratings (БД)
            if secid in ratings_map:
                bond["RATINGS"] = ratings_map[secid].get("all_ratings", [])
            # 2) Если рейтинг не установлен — из emitent_ratings по эмитенту (БД)
            if secid in emitent_map:
                emitent_entry = emitent_map[secid]
                bond["BONDTYPE"] = emitent_entry.get("type")
                if not bond.get("RATINGS"):
                    bond["RATINGS"] = emitent_entry.get("cci_rating_companies", []) or []
            # 3) Стандартизация рейтинга и запись в структуру для сохранения в БД
            if bond.get("RATINGS"):
                worst_rating = self._get_worst_rating(bond["RATINGS"])
                if worst_rating:
                    bond["RATING_AGENCY"] = worst_rating.get("agency_name_short_ru", "").strip()
                    rating_level_raw = worst_rating.get("rating_level_name_short_ru", "").strip()
                    bond["RATING_LEVEL"] = standardize_rating(rating_level_raw) or rating_level_raw

        return raw_bonds_data

    def _load_ratings_map(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Загружает рейтинги облигаций из БД (bond_ratings + bonds + rating_agency).

        Один запрос с JOIN: bonds.secid, rating_agency.agency_name_short_ru,
        bond_ratings.rating_level_name. Для secid без рейтингов в словаре записи нет
        (при обращении вернуть пустой список).

        Returns:
            Словарь: ключ — secid, значение — {"all_ratings": [{"agency_name_short_ru", "rating_level_name", "rating_level_name_short_ru"}, ...]}.
        """
        ratings_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        try:
            # JOIN bond_ratings -> bonds (по bond_id) и rating_agency (по agency_id = rating_agency.agency_id)
            stmt = (
                select(Bond.secid, RatingAgency.agency_name_short_ru, BondRating.rating_level_name)
                .join(BondRating, Bond.id == BondRating.bond_id)
                .join(RatingAgency, BondRating.agency_id == RatingAgency.agency_id)
            )
            rows = self.session.exec(stmt).all()
            for secid, agency_name_short_ru, rating_level_name in rows:
                if not secid:
                    continue
                name_ru = (agency_name_short_ru or "").strip()
                level = (rating_level_name or "").strip()
                if not name_ru:
                    continue
                entry = {
                    "agency_name_short_ru": name_ru,
                    "rating_level_name": level,
                    "rating_level_name_short_ru": level,
                }
                if secid not in ratings_map:
                    ratings_map[secid] = {"all_ratings": []}
                ratings_map[secid]["all_ratings"].append(entry)
        except Exception as e:
            self.logger.warning("Ошибка при загрузке рейтингов из БД: %s", e)
        return ratings_map

    def _load_emitent_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные эмитентов из БД (bonds -> emitents -> emitent_ratings -> rating_agency).

        Один запрос с JOIN по secid. Извлекает type из emitents, cci_rating_companies —
        список словарей с agency_name_short_ru и rating_level_name_short_ru для совместимости
        с _get_worst_rating.

        Returns:
            Словарь: ключ — secid, значение — {"type": str|None, "cci_rating_companies": [...]}.
        """
        emitent_map: Dict[str, Dict[str, Any]] = {}
        try:
            # Bond -> Emitent (emitent_id), EmitentRating (emitent_id), RatingAgency (agency_id = rating_agency.id)
            stmt = (
                select(
                    Bond.secid,
                    Emitent.type,
                    RatingAgency.agency_name_short_ru,
                    EmitentRating.rating_level_name,
                )
                .join(Emitent, Bond.emitent_id == Emitent.id)
                .join(EmitentRating, EmitentRating.emitent_id == Emitent.id)
                .join(RatingAgency, EmitentRating.agency_id == RatingAgency.id)
            )
            rows = self.session.exec(stmt).all()
            for secid, emitent_type, agency_name_short_ru, rating_level_name in rows:
                if not secid:
                    continue
                name_ru = (agency_name_short_ru or "").strip()
                level = (rating_level_name or "").strip() if rating_level_name else ""
                if secid not in emitent_map:
                    type_val = (emitent_type or "").strip() or None
                    emitent_map[secid] = {"type": type_val, "cci_rating_companies": []}
                emitent_map[secid]["cci_rating_companies"].append({
                    "agency_name_short_ru": name_ru,
                    "rating_level_name_short_ru": level,
                })
        except Exception as e:
            self.logger.warning("Ошибка при загрузке данных эмитентов из БД: %s", e)
        return emitent_map

    def _load_coupons_map(self) -> Dict[str, Dict[str, Any]]:
        """Заглушка: данные о купонах хранятся только в БД (таблица coupons).

        Источник истины для купонов — DBCoupon. Метод оставлен для совместимости
        вызовов; возвращает пустой словарь.

        Returns:
            Пустой словарь (купоны запрашиваются через CouponService/DBCoupon).
        """
        return {}

    def _get_worst_rating(self, ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Определяет наихудший рейтинг из списка рейтингов.

        Args:
            ratings_list: Список словарей с рейтингами.

        Returns:
            Словарь с наихудшим рейтингом или None.
        """
        if not ratings_list:
            return None
        non_revoked = [
            r for r in ratings_list
            if isinstance(r, dict)
            and (r.get("rating_level_name_short_ru") or "").lower() not in ("отозван", "отозвано")
        ]
        ratings_to_check = non_revoked if non_revoked else ratings_list
        if not ratings_to_check:
            return None
        worst_rating = None
        worst_index = -1
        for rating in ratings_to_check:
            level = (rating.get("rating_level_name_short_ru") or "").strip()
            if not level:
                continue
            idx = get_rating_index(level)
            if idx is not None and idx > worst_index:
                worst_index = idx
                worst_rating = rating
        return worst_rating

    def _get_bond_rating(
        self,
        raw_data: Dict[str, Any],
        emitent_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Возвращает рейтинг облигации для записи в БД.

        Использует RATING_LEVEL, если уже задан (стандартизация выполняется
        в prepare_bonds_for_db). Иначе вычисляет из RATINGS/emitent_data
        и применяет стандартизацию через standardize_rating перед возвратом.
        """
        rating_level = raw_data.get("RATING_LEVEL")
        if rating_level and str(rating_level).strip():
            return str(rating_level).strip()
        ratings = raw_data.get("RATINGS", [])
        if not ratings and emitent_data:
            ratings = emitent_data.get("cci_rating_companies", []) or []
        if not ratings:
            return None
        worst = self._get_worst_rating(ratings)
        if worst:
            level = (worst.get("rating_level_name_short_ru") or "").strip()
            if level:
                return standardize_rating(level) or level
        return None

    @staticmethod
    def _calculate_coupon_frequency(coupon_period: Optional[int]) -> Optional[float]:
        """Вычисляет частоту купона (число выплат в год).

        Args:
            coupon_period: Период купона в днях.

        Returns:
            Частота купона (округлённая) или None.
        """
        if coupon_period is None or coupon_period == 0:
            return None
        try:
            return round(365 / coupon_period)
        except (ZeroDivisionError, TypeError):
            return None

    def transform_to_bond(
        self,
        raw_data: Dict[str, Any],
        type_mapping: Dict[str, int],
        kind_mapping: Dict[str, int],
    ) -> Optional[Bond]:
        """Преобразует сырые данные в объект Bond со всеми рассчитанными показателями.

        Выполняет все расчёты: рейтинг, частота купона, дюрация в годах,
        флаги оферт, доходность купона к цене, маппинг типов/видов, даты.
        Возвращает полностью заполненный Bond для сохранения в БД.

        Args:
            raw_data: Словарь с сырыми данными облигации из JSON.
            type_mapping: Маппинг типов облигаций (строка -> ID).
            kind_mapping: Маппинг видов облигаций (строка -> ID).

        Returns:
            Объект Bond с рассчитанными полями или None, если SECID отсутствует.
        """
        secid = raw_data.get("SECID")
        if not secid:
            return None

        emitent_data = None
        try:
            emitent_svc = get_emitent_service()
            if emitent_svc:
                emitent_data = emitent_svc.get_emitent_by_secid(secid)
        except Exception:
            pass
        rating = self._get_bond_rating(raw_data, emitent_data)

        coupon_period = raw_data.get("COUPONPERIOD")
        coupon_frequency = self._calculate_coupon_frequency(coupon_period)

        duration = raw_data.get("DURATION")
        duration_years = None
        if duration is not None:
            try:
                duration_years = round(float(duration) / 365, 2)
            except (TypeError, ZeroDivisionError):
                pass

        has_put_option = 1 if raw_data.get("PUTOPTIONDATE") else 0
        has_call_option = 1 if raw_data.get("CALLOPTIONDATE") else 0

        current_price = raw_data.get("PRICE") or raw_data.get("PREVPRICE") or raw_data.get("PREVWAPRICE")
        yield_to_maturity = raw_data.get("YIELDATPREVWAPRICE")

        coupon_yield_to_price = None
        coupon_value = raw_data.get("COUPONVALUE")
        face_value = raw_data.get("FACEVALUE")
        if (
            coupon_value is not None
            and current_price is not None
            and face_value is not None
            and coupon_period
            and coupon_period > 0
        ):
            try:
                payments_per_year = 365 / coupon_period
                if current_price > 0 and face_value > 0:
                    coupon_yield_to_price = (
                        (coupon_value * 10000 / (current_price * face_value)) * payments_per_year
                    )
            except (ZeroDivisionError, TypeError):
                pass

        bond_type_str = raw_data.get("BONDTYPE")
        bond_type = type_mapping.get(bond_type_str) if bond_type_str in type_mapping else None

        bond_kind_str = raw_data.get("BONDTYPE43")
        bond_kind = None
        if bond_kind_str:
            bond_kind_str = str(bond_kind_str).strip()
            if bond_kind_str in kind_mapping:
                bond_kind = kind_mapping[bond_kind_str]

        def _fmt_date(val: Any) -> Optional[str]:
            if val is None:
                return None
            if isinstance(val, date):
                return val.strftime("%Y-%m-%d")
            if isinstance(val, str) and val and val != "0000-00-00":
                return val
            return None

        maturity_date = _fmt_date(raw_data.get("MATDATE"))
        offer_date = _fmt_date(raw_data.get("OFFERDATE"))
        next_coupon = _fmt_date(raw_data.get("NEXTCOUPON"))
        call_option_date = _fmt_date(raw_data.get("CALLOPTIONDATE"))
        put_option_date = _fmt_date(raw_data.get("PUTOPTIONDATE"))

        rating_agency: Optional[str] = None
        ratings_list = raw_data.get("RATINGS") or []
        if isinstance(ratings_list, list) and ratings_list:
            worst = self._get_worst_rating(ratings_list)
            if worst:
                rating_agency = (worst.get("agency_name_short_ru") or "").strip()

        duration_waprice = raw_data.get("DURATIONWAPRICE")
        if duration_waprice is not None and not isinstance(duration_waprice, int):
            try:
                duration_waprice = int(duration_waprice)
            except (TypeError, ValueError):
                duration_waprice = None

        currency_val = raw_data.get("CURRENCYID")
        face_unit_val = raw_data.get("FACEUNIT")

        return Bond(
            secid=secid,
            boardid=raw_data.get("BOARDID"),
            isin=raw_data.get("ISIN"),
            name=raw_data.get("SHORTNAME") or raw_data.get("SECNAME"),
            secname=raw_data.get("SECNAME"),
            rating=rating,
            rating_agency=rating_agency,
            current_price=current_price,
            coupon_yield_to_price=coupon_yield_to_price,
            yield_to_maturity=yield_to_maturity,
            face_value=face_value,
            currency=currency_val,
            face_unit=face_unit_val,
            coupon_value=coupon_value,
            coupon_percent=raw_data.get("COUPONPERCENT"),
            coupon_frequency=coupon_frequency,
            coupon_period=raw_data.get("COUPONPERIOD"),
            accrued_interest=raw_data.get("ACCRUEDINT"),
            duration_years=duration_years,
            duration=float(duration) if duration is not None else None,
            duration_waprice=duration_waprice,
            has_put_option=has_put_option,
            has_call_option=has_call_option,
            maturity_date=maturity_date,
            listing_level=raw_data.get("LISTLEVEL"),
            bond_type=bond_type,
            bond_kind=bond_kind,
            offer_date=offer_date,
            status=raw_data.get("STATUS"),
            trading_status=raw_data.get("TRADINGSTATUS"),
            next_coupon=next_coupon,
            board_name=raw_data.get("BOARDNAME"),
            call_option_date=call_option_date,
            put_option_date=put_option_date,
            emitent_id=None,
        )

    def transform_batch(self, raw_bonds_list: List[Dict[str, Any]]) -> List[Bond]:
        """Преобразует список сырых облигаций в список объектов Bond.

        Для каждой записи выполняет все расчёты через transform_to_bond
        и возвращает готовые объекты для сохранения в БД.

        Args:
            raw_bonds_list: Список словарей с сырыми данными (результат prepare_bonds_for_db).

        Returns:
            Список объектов Bond, готовых для передачи в bonds_repository.save_bonds.
        """
        type_mapping, kind_mapping = self.load_mappings()
        result: List[Bond] = []
        for bond_data in raw_bonds_list:
            try:
                bond = self.transform_to_bond(bond_data, type_mapping, kind_mapping)
                if bond:
                    result.append(bond)
            except Exception as e:
                self.logger.warning(
                    "Ошибка при преобразовании облигации %s: %s",
                    bond_data.get("SECID", "unknown"),
                    e,
                )
        return result

    @staticmethod
    def _parse_date_for_security(val: Any) -> Optional[date]:
        """Парсит значение в date для полей BondSecurity.

        Args:
            val: Строка даты (YYYY-MM-DD), date или None.

        Returns:
            date или None при некорректном значении.
        """
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, str) and val.strip() and val.strip() != "0000-00-00":
            try:
                return date.fromisoformat(val.strip()[:10])
            except ValueError:
                pass
        return None

    def transform_to_bond_security(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Преобразует сырые данные секции securities в словарь для вставки.

        Извлекает поля из merged bond_dict (securities). Возвращает словарь
        с secid, boardid и всеми полями BondSecurity (без bond_id).
        bond_id подставляется через подзапрос при сохранении.

        Args:
            raw_data: Словарь с сырыми данными (результат prepare_bonds_for_db).

        Returns:
            Словарь с secid, boardid и полями BondSecurity или None, если SECID отсутствует.
        """
        secid = raw_data.get("SECID")
        if not secid:
            return None
        boardid = self._safe_str(raw_data.get("BOARDID"))
        return {
            "secid": secid,
            "boardid": boardid,
            "prev_waprice": self._safe_float(raw_data.get("PREVWAPRICE")),
            "yield_at_prev_waprice": self._safe_float(raw_data.get("YIELDATPREVWAPRICE")),
            "prev_price": self._safe_float(raw_data.get("PREVPRICE")),
            "lot_size": self._safe_int(raw_data.get("LOTSIZE")),
            "reg_number": self._safe_str(raw_data.get("REGNUMBER")),
            "decimals": self._safe_int(raw_data.get("DECIMALS")),
            "issue_size": self._safe_int(raw_data.get("ISSUESIZE")),
            "prev_legal_close_price": self._safe_float(raw_data.get("PREVLEGALCLOSEPRICE")),
            "prev_date": self._parse_date_for_security(raw_data.get("PREVDATE")),
            "remarks": self._safe_str(raw_data.get("REMARKS")),
            "market_code": self._safe_str(raw_data.get("MARKETCODE")),
            "instr_id": self._safe_str(raw_data.get("INSTRID")),
            "sector_id": self._safe_str(raw_data.get("SECTORID")),
            "min_step": self._safe_float(raw_data.get("MINSTEP")),
            "face_unit": self._safe_str(raw_data.get("FACEUNIT")),
            "buyback_price": self._safe_float(raw_data.get("BUYBACKPRICE")),
            "buyback_date": self._parse_date_for_security(raw_data.get("BUYBACKDATE")),
            "lat_name": self._safe_str(raw_data.get("LATNAME")),
            "issue_size_placed": self._safe_int(raw_data.get("ISSUESIZEPLACED")),
            "sec_type": self._safe_str(raw_data.get("SECTYPE")),
            "settle_date": self._parse_date_for_security(raw_data.get("SETTLEDATE")),
            "lot_value": self._safe_float(raw_data.get("LOTVALUE")),
            "face_value_on_settle_date": self._safe_float(raw_data.get("FACEVALUEONSETTLEDATE")),
            "date_yield_from_issuer": self._parse_date_for_security(raw_data.get("DATEYIELDFROMISSUER")),
        }

    def transform_to_bond_market_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Преобразует сырые данные секции marketdata в словарь для вставки.

        Возвращает словарь с secid, boardid и полями BondMarketData (без bond_id).
        bond_id подставляется через подзапрос при сохранении.

        Args:
            raw_data: Словарь с сырыми данными (результат prepare_bonds_for_db).

        Returns:
            Словарь с secid, boardid и полями BondMarketData или None, если SECID отсутствует.
        """
        secid = raw_data.get("SECID")
        if not secid:
            return None
        boardid = self._safe_str(raw_data.get("BOARDID"))
        return {
            "secid": secid,
            "boardid": boardid,
            "bid": self._safe_float(raw_data.get("BID")),
            "offer": self._safe_float(raw_data.get("OFFER")),
            "spread": self._safe_float(raw_data.get("SPREAD")),
            "bid_depth": self._safe_int(raw_data.get("BIDDEPTH")),
            "offer_depth": self._safe_int(raw_data.get("OFFERDEPTH")),
            "open_price": self._safe_float(raw_data.get("OPEN")),
            "low": self._safe_float(raw_data.get("LOW")),
            "high": self._safe_float(raw_data.get("HIGH")),
            "last_price": self._safe_float(raw_data.get("LAST")),
            "last_change": self._safe_float(raw_data.get("LASTCHANGE")),
            "last_change_prcnt": self._safe_float(raw_data.get("LASTCHANGEPRCNT")),
            "qty": self._safe_int(raw_data.get("QTY")),
            "value": self._safe_float(raw_data.get("VALUE")),
            "value_usd": self._safe_float(raw_data.get("VALUE_USD")),
            "waprice": self._safe_float(raw_data.get("WAPRICE")),
            "last_cnt_to_last_waprice": self._safe_float(raw_data.get("LASTCNGTOLASTWAPRICE")),
            "wap_to_prev_waprice_prcnt": self._safe_float(raw_data.get("WAPTOPREVWAPRICEPRCNT")),
            "wap_to_prev_waprice": self._safe_float(raw_data.get("WAPTOPREVWAPRICE")),
            "close_price": self._safe_float(raw_data.get("CLOSEPRICE")),
            "market_price_today": self._safe_float(raw_data.get("MARKETPRICETODAY")),
            "market_price": self._safe_float(raw_data.get("MARKETPRICE")),
            "last_to_prev_price": self._safe_float(raw_data.get("LASTTOPREVPRICE")),
            "num_trades": self._safe_int(raw_data.get("NUMTRADES")),
            "vol_today": self._safe_int(raw_data.get("VOLTODAY")),
            "val_today": self._safe_float(raw_data.get("VALTODAY")),
            "val_today_usd": self._safe_float(raw_data.get("VALTODAY_USD")),
            "etf_settle_price": self._safe_float(raw_data.get("ETFSETTLEPRICE")),
            "update_time": self._safe_str(raw_data.get("UPDATETIME")),
        }

    @staticmethod
    def _safe_float(val: Any) -> Optional[float]:
        """Преобразует значение в float или возвращает None."""
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(val: Any) -> Optional[int]:
        """Преобразует значение в int или возвращает None."""
        if val is None:
            return None
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_str(val: Any) -> Optional[str]:
        """Возвращает непустую строку или None."""
        if val is None:
            return None
        s = str(val).strip()
        return s if s else None

    def transform_to_bond_securities_batch(
        self, raw_bonds_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Преобразует список сырых облигаций в список словарей для BondSecurity.

        Args:
            raw_bonds_list: Список словарей с сырыми данными.

        Returns:
            Список словарей с secid, boardid и полями BondSecurity.
        """
        result: List[Dict[str, Any]] = []
        for bond_data in raw_bonds_list:
            try:
                obj = self.transform_to_bond_security(bond_data)
                if obj:
                    result.append(obj)
            except Exception as e:
                self.logger.warning(
                    "Ошибка при преобразовании BondSecurity %s: %s",
                    bond_data.get("SECID", "unknown"),
                    e,
                )
        return result

    def transform_to_bond_market_data_batch(
        self, raw_bonds_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Преобразует список сырых облигаций в список словарей для BondMarketData.

        Args:
            raw_bonds_list: Список словарей с сырыми данными.

        Returns:
            Список словарей с secid, boardid и полями BondMarketData.
        """
        result: List[Dict[str, Any]] = []
        for bond_data in raw_bonds_list:
            try:
                obj = self.transform_to_bond_market_data(bond_data)
                if obj:
                    result.append(obj)
            except Exception as e:
                self.logger.warning(
                    "Ошибка при преобразовании BondMarketData %s: %s",
                    bond_data.get("SECID", "unknown"),
                    e,
                )
        return result

    def transform_to_bond_market_data_yield(
        self, raw_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Преобразует сырые данные секции marketdata_yields в словарь для вставки.

        Возвращает словарь с secid, boardid и полями BondMarketDataYield (без bond_id).
        bond_id подставляется через подзапрос при сохранении.

        Args:
            raw_data: Словарь с сырыми данными (результат prepare_bonds_for_db).

        Returns:
            Словарь с secid, boardid и полями BondMarketDataYield или None.
        """
        secid = raw_data.get("SECID")
        if not secid:
            return None
        if raw_data.get("EFFECTIVEYIELD") is None and raw_data.get("YIELDDATETYPE") is None:
            return None
        boardid = self._safe_str(raw_data.get("BOARDID"))
        return {
            "secid": secid,
            "boardid": boardid,
            "price": self._safe_float(raw_data.get("PRICE")),
            "yield_date": self._safe_str(raw_data.get("YIELDDATE")),
            "zcyc_moment": self._safe_str(raw_data.get("ZCYCMOMENT")),
            "yield_date_type": self._safe_str(raw_data.get("YIELDDATETYPE")),
            "effective_yield": self._safe_float(raw_data.get("EFFECTIVEYIELD")),
            "duration": self._safe_int(raw_data.get("DURATION")),
            "zspread_bp": self._safe_int(raw_data.get("ZSPREADBP")),
            "gspread_bp": self._safe_int(raw_data.get("GSPREADBP")),
            "waprice": self._safe_float(raw_data.get("WAPRICE")),
            "effective_yield_waprice": self._safe_float(raw_data.get("EFFECTIVEYIELDWAPRICE")),
            "duration_waprice": self._safe_int(raw_data.get("DURATIONWAPRICE")),
            "ir": self._safe_float(raw_data.get("IR")),
            "icpi": self._safe_float(raw_data.get("ICPI")),
            "bei": self._safe_float(raw_data.get("BEI")),
            "cbr": self._safe_float(raw_data.get("CBR")),
            "yield_to_offer": self._safe_float(raw_data.get("YIELDTOOFFER")),
            "yield_last_coupon": self._safe_float(raw_data.get("YIELDLASTCOUPON")),
            "trade_moment": self._safe_str(raw_data.get("TRADEMOMENT")),
            "seqnum": self._safe_int(raw_data.get("SEQNUM")),
            "systime": self._safe_str(raw_data.get("SYSTIME")),
        }

    def transform_to_bond_market_data_yields_batch(
        self, raw_bonds_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Преобразует список сырых облигаций в список словарей для BondMarketDataYield.

        Args:
            raw_bonds_list: Список словарей с сырыми данными.

        Returns:
            Список словарей с secid, boardid и полями BondMarketDataYield.
        """
        result: List[Dict[str, Any]] = []
        for bond_data in raw_bonds_list:
            try:
                obj = self.transform_to_bond_market_data_yield(bond_data)
                if obj:
                    result.append(obj)
            except Exception as e:
                self.logger.warning(
                    "Ошибка при преобразовании BondMarketDataYield %s: %s",
                    bond_data.get("SECID", "unknown"),
                    e,
                )
        return result
