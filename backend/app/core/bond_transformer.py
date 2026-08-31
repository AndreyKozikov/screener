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
        skipped_matured_count = 0

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

        self.logger.debug(
            "Преобразовано из payload: %s облигаций, пропущено погашенных: %s",
            len(bonds_data),
            skipped_matured_count,
        )
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





