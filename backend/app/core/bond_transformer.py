"""Центральный модуль расчётной логики облигаций.

Содержит класс BondTransformer: загрузка маппингов, объединение данных из JSON,
расчёт доходности, дюрации, рейтингов, флагов оферт и преобразование сырых
данных в объекты Bond для сохранения в БД. Вся бизнес-логика расчётов
сосредоточена здесь; в БД сохраняются только физически рассчитанные значения.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.models.bond import Bond
from app.repository.files.file_storage import FileStorage
from config.paths import (
    BONDS_EMITENT_JSON,
    BONDS_JSON,
    BONDS_RATING_JSON,
    BONDS_TYPE_MAPPING_JSON,
    BONDS_TYPE43_MAPPING_JSON,
    COUPONS_DATA_JSON,
)
from app.services.bond_filter import get_rating_index, standardize_rating
from app.services.emitent_service import get_emitent_service


class BondTransformer:
    """Преобразование данных облигаций из JSON в формат таблицы БД.

    Загружает маппинги типов и видов облигаций из JSON, объединяет данные
    из bonds.json, bonds_rating.json, bonds_emitent.json и coupons_data.json,
    вычисляет рейтинги и производные поля и формирует словари для вставки в БД.

    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
        storage: Хранилище для чтения JSON файлов.
    """

    def __init__(self, data_dir: Path, storage: FileStorage):
        """Инициализирует преобразователь данных облигаций.

        Args:
            data_dir: Путь к директории с JSON файлами (bonds.json, маппинги и т.д.).
            storage: Экземпляр FileStorage для чтения JSON.
        """
        self.data_dir = Path(data_dir)
        self.storage = storage
        self.logger = logging.getLogger(__name__)

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

    def prepare_bonds_for_db(self) -> List[Dict[str, Any]]:
        """Загружает данные облигаций из JSON-файлов и объединяет их.

        Читает bonds.json, объединяет секции securities, marketdata и marketdata_yields.
        Рейтинг: сначала из bonds_rating.json; если не установлен — из bonds_emitent.json
        (cci_rating_companies). После выбора источника выполняется стандартизация рейтинга
        и запись в структуру для сохранения в БД. Добавляет типы из bonds_emitent.json
        и значения купонов из coupons_data.json (через CouponLoader).

        Returns:
            Список словарей с данными облигаций (по одному на облигацию),
            готовых для передачи в transform_batch.
        """
        bonds_data: List[Dict[str, Any]] = []
        bonds_path = self.data_dir / BONDS_JSON

        if not bonds_path.exists():
            self.logger.error("Файл bonds.json не найден: %s", bonds_path)
            return bonds_data

        try:
            data = self.storage.read_json(bonds_path)
        except Exception as e:
            self.logger.error("Ошибка при загрузке bonds.json: %s", e, exc_info=True)
            return bonds_data

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

        self.logger.debug("Загружено %s облигаций из bonds.json", len(bonds_data))

        ratings_map = self._load_ratings_map()
        emitent_map = self._load_emitent_map()
        for bond in bonds_data:
            secid = bond.get("SECID")
            if not secid:
                continue
            # 1) Рейтинг: сначала из bonds_rating.json
            if secid in ratings_map:
                bond["RATINGS"] = ratings_map[secid].get("all_ratings", [])
            # 2) Если рейтинг не установлен — из bonds_emitent.json
            if secid in emitent_map:
                bond["BONDTYPE"] = emitent_map[secid].get("type")
                if not bond.get("RATINGS"):
                    bond["RATINGS"] = emitent_map[secid].get("cci_rating_companies", []) or []
            # 3) Стандартизация рейтинга и запись в структуру для сохранения в БД
            if bond.get("RATINGS"):
                worst_rating = self._get_worst_rating(bond["RATINGS"])
                if worst_rating:
                    bond["RATING_AGENCY"] = worst_rating.get("agency_name_short_ru", "").strip()
                    rating_level_raw = worst_rating.get("rating_level_name_short_ru", "").strip()
                    bond["RATING_LEVEL"] = standardize_rating(rating_level_raw) or rating_level_raw

        coupons_map = self._load_coupons_map()
        from app.services.coupon_loader import get_coupon_loader

        coupon_loader = get_coupon_loader()
        for bond in bonds_data:
            secid = bond.get("SECID")
            if secid and secid in coupons_map:
                bond_data = coupons_map[secid]
                coupons = bond_data.get("coupons", [])
                if coupons and coupon_loader:
                    coupon_value = coupon_loader.get_nearest_coupon_value(secid)
                    if coupon_value is not None:
                        bond["COUPONVALUE"] = coupon_value

        return bonds_data

    def _load_ratings_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает рейтинги облигаций из bonds_rating.json.

        Returns:
            Словарь, где ключ — SECID, значение — словарь с ключом "all_ratings".
        """
        ratings_map: Dict[str, Dict[str, Any]] = {}
        path = self.data_dir / BONDS_RATING_JSON
        if not path.exists():
            return ratings_map
        try:
            ratings_data = self.storage.read_json(path)
            if not isinstance(ratings_data, dict):
                return ratings_map
            for secid, rating_entry in ratings_data.items():
                if isinstance(rating_entry, dict):
                    ratings_list = rating_entry.get("ratings") or rating_entry.get("all_ratings", [])
                elif isinstance(rating_entry, list):
                    ratings_list = rating_entry
                else:
                    continue
                if isinstance(ratings_list, list) and len(ratings_list) > 0:
                    valid = [
                        r for r in ratings_list
                        if isinstance(r, dict) and (r.get("agency_name_short_ru") or "").strip()
                    ]
                    if valid:
                        ratings_map[secid] = {"all_ratings": valid}
        except Exception as e:
            self.logger.warning("Ошибка при загрузке рейтингов: %s", e)
        return ratings_map

    def _load_emitent_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные эмитентов из bonds_emitent.json.

        Returns:
            Словарь, где ключ — SECID, значение — словарь с данными эмитента.
        """
        emitent_map: Dict[str, Dict[str, Any]] = {}
        path = self.data_dir / BONDS_EMITENT_JSON
        if not path.exists():
            return emitent_map
        try:
            emitent_data = self.storage.read_json(path)
            if isinstance(emitent_data, dict):
                for secid, entry in emitent_data.items():
                    if isinstance(entry, dict):
                        emitent_map[secid] = entry
        except Exception as e:
            self.logger.warning("Ошибка при загрузке данных эмитентов: %s", e)
        return emitent_map

    def _load_coupons_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные о купонах из coupons_data.json.

        Returns:
            Словарь, где ключ — SECID, значение — словарь с данными о купонах.
        """
        coupons_map: Dict[str, Dict[str, Any]] = {}
        path = self.data_dir / COUPONS_DATA_JSON
        if not path.exists():
            return coupons_map
        try:
            coupons_data = self.storage.read_json(path)
            if isinstance(coupons_data, dict):
                bonds_data = coupons_data.get("bonds", {})
                if isinstance(bonds_data, dict):
                    for secid, bond_data in bonds_data.items():
                        if isinstance(bond_data, dict):
                            coupons_map[secid] = bond_data
        except Exception as e:
            self.logger.warning("Ошибка при загрузке данных о купонах: %s", e)
        return coupons_map

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
        без повторной стандартизации.
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
                return level
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

        return Bond(
            secid=secid,
            boardid=raw_data.get("BOARDID"),
            isin=raw_data.get("ISIN"),
            name=raw_data.get("SHORTNAME") or raw_data.get("SECNAME"),
            rating=rating,
            current_price=current_price,
            coupon_yield_to_price=coupon_yield_to_price,
            yield_to_maturity=yield_to_maturity,
            face_value=face_value,
            currency=raw_data.get("FACEUNIT"),
            coupon_value=coupon_value,
            coupon_percent=raw_data.get("COUPONPERCENT"),
            coupon_frequency=coupon_frequency,
            accrued_interest=raw_data.get("ACCRUEDINT"),
            duration_years=duration_years,
            has_put_option=has_put_option,
            has_call_option=has_call_option,
            maturity_date=maturity_date,
            listing_level=raw_data.get("LISTLEVEL"),
            bond_type=bond_type,
            bond_kind=bond_kind,
            offer_date=offer_date,
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
