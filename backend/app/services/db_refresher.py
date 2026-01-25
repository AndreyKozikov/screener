import sqlite3
import logging
import csv
import math
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from datetime import date, datetime

import orjson

from app.services.bond_filter import get_rating_index, RATINGS, standardize_rating
from app.models.filters import BondFilters
from app.services.emitent_service import get_emitent_service
from app.services.coupon_loader import get_coupon_loader


# Константа со списком всех возможных рейтингов в строгом иерархическом порядке
# От наивысшего (AAA) до наинизшего (D)
RATINGS_ORDER = [
    'AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 
    'BBB+', 'BBB', 'BBB-', 'BB+', 'BB', 'BB-', 
    'B+', 'B', 'B-', 'CCC', 'CC', 'C', 'D'
]


class DBBonds:
    """
    Слой данных: работа с БД облигаций.

    - refresh(): создание/обновление таблицы bonds из JSON (миграции).
    - fetch_bonds_raw(), count_bonds(): только SQL-запросы, возврат сырых данных.
    Вся бизнес-логика, преобразования и фильтры по рейтингу/эмитенту — в сервисном слое.
    """
    
    def __init__(self, db_path: Optional[Path] = None, data_dir: Optional[Path] = None):
        """
        Инициализация сервиса
        
        Args:
            db_path: Путь к файлу базы данных. Если не указан, используется backend/db/bonds.db
            data_dir: Путь к директории с JSON-файлами. Если не указан, используется backend/app/data
        """
        if db_path is None:
            # Определяем путь относительно текущего файла
            backend_dir = Path(__file__).parent.parent.parent
            db_path = backend_dir / "db" / "bonds.db"
        
        if data_dir is None:
            backend_dir = Path(__file__).parent.parent.parent
            data_dir = backend_dir / "app" / "data"
        
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.logger = logging.getLogger(__name__)
    
    def refresh(self) -> bool:
        """
        Публичная точка входа для создания или обновления таблицы bonds в базе данных.
        
        Returns:
            True если операция выполнена успешно, False в случае ошибки
        """
        try:
            self._ensure_db_directory()
            
            # Проверяем существование таблицы
            if not self._table_exists("bonds"):
                self.logger.info("Таблица bonds не существует, создаём её")
                self._create_bonds_table()
            else:
                self.logger.info("Таблица bonds существует, обновляем данные")
            
            # Загружаем маппинги
            type_mapping, kind_mapping = self._load_mappings()
            self.logger.debug(f"Загружены маппинги: типов - {len(type_mapping)}, видов - {len(kind_mapping)}")
            self.logger.debug(f"Ключи в маппинге видов: {list(kind_mapping.keys())}")
            
            # Загружаем данные из JSON
            bonds_data = self._load_json_data()
            self.logger.info(f"Загружено {len(bonds_data)} облигаций из JSON-файлов")
            
            # Преобразуем данные
            transformed_bonds = []
            for bond_data in bonds_data:
                try:
                    transformed = self._transform_bond_data(bond_data, type_mapping, kind_mapping)
                    if transformed:
                        transformed_bonds.append(transformed)
                except Exception as e:
                    self.logger.warning(f"Ошибка при преобразовании данных облигации {bond_data.get('SECID', 'unknown')}: {e}")
                    continue
            
            self.logger.info(f"Преобразовано {len(transformed_bonds)} облигаций")
            
            # Вставляем или заменяем записи
            self._insert_or_replace_bonds(transformed_bonds)
            
            self.logger.info(f"Таблица bonds успешно создана/обновлена в базе данных: {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при создании/обновлении таблицы bonds: {str(e)}", exc_info=True)
            return False
    
    def _ensure_db_directory(self) -> None:
        """Создает директорию для базы данных, если она не существует"""
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Директория для БД проверена/создана: {db_dir}")
    
    def _table_exists(self, table_name: str) -> bool:
        """Проверяет существование таблицы в базе данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Ошибка при проверке существования таблицы: {e}")
            return False

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        """Проверяет существование колонки в таблице (для совместимости со старыми схемами)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(%s)" % table_name)
                for row in cursor.fetchall():
                    if row[1] == column_name:
                        return True
                return False
        except Exception as e:
            self.logger.error(f"Ошибка при проверке колонки {column_name}: {e}")
            return False
    
    def _create_bonds_table(self) -> None:
        """Создает таблицу bonds с заданной структурой"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bonds (
            secid TEXT PRIMARY KEY,
            boardid TEXT,
            isin TEXT,
            name TEXT,
            rating TEXT,
            current_price REAL,
            coupon_yield_to_price REAL,
            yield_to_maturity REAL,
            face_value REAL,
            currency TEXT,
            coupon_value REAL,
            coupon_percent REAL,
            coupon_frequency REAL,
            accrued_interest REAL,
            duration_years REAL,
            has_put_option INTEGER,
            has_call_option INTEGER,
            maturity_date TEXT,
            listing_level INTEGER,
            bond_type INTEGER,
            bond_kind INTEGER,
            offer_date TEXT
        )
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            self.logger.debug("SQL запрос CREATE TABLE для bonds выполнен успешно")
    
    def _load_mappings(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Загружает маппинги типов и видов облигаций из JSON-файлов.
        
        Returns:
            Кортеж (type_mapping, kind_mapping)
        """
        type_mapping = {}
        kind_mapping = {}
        
        # Загружаем маппинг типов облигаций
        type_mapping_path = self.data_dir / "bonds_type_mapping.json"
        if type_mapping_path.exists():
            try:
                with open(type_mapping_path, 'rb') as f:
                    type_mapping = orjson.loads(f.read())
                self.logger.debug(f"Загружен маппинг типов: {len(type_mapping)} записей")
            except Exception as e:
                self.logger.warning(f"Ошибка при загрузке маппинга типов: {e}")
        
        # Загружаем маппинг видов облигаций
        kind_mapping_path = self.data_dir / "bonds_type43_mapping.json"
        if kind_mapping_path.exists():
            try:
                with open(kind_mapping_path, 'rb') as f:
                    kind_mapping = orjson.loads(f.read())
                self.logger.debug(f"Загружен маппинг видов: {len(kind_mapping)} записей")
            except Exception as e:
                self.logger.warning(f"Ошибка при загрузке маппинга видов: {e}")
        
        return type_mapping, kind_mapping
    
    def _load_json_data(self) -> List[Dict[str, Any]]:
        """
        Загружает данные облигаций из JSON-файлов и объединяет их.
        
        Returns:
            Список словарей с данными облигаций
        """
        bonds_data = []
        
        # Загружаем основной файл bonds.json
        bonds_path = self.data_dir / "bonds.json"
        if not bonds_path.exists():
            self.logger.error(f"Файл bonds.json не найден: {bonds_path}")
            return bonds_data
        
        try:
            with open(bonds_path, 'rb') as f:
                data = orjson.loads(f.read())
            
            # Парсим секции
            securities = data.get("securities", {})
            sec_columns = securities.get("columns", [])
            sec_data = securities.get("data", [])
            
            marketdata = data.get("marketdata", {})
            md_columns = marketdata.get("columns", [])
            md_data = marketdata.get("data", [])
            
            yields = data.get("marketdata_yields", {})
            yields_columns = yields.get("columns", [])
            yields_data = yields.get("data", [])
            
            # Создаём словари для быстрого поиска
            marketdata_map = {}
            for row in md_data:
                md_dict = dict(zip(md_columns, row))
                secid = md_dict.get("SECID")
                if secid:
                    marketdata_map[secid] = md_dict
            
            yields_map = {}
            for row in yields_data:
                yields_dict = dict(zip(yields_columns, row))
                secid = yields_dict.get("SECID")
                if secid and secid not in yields_map:
                    yields_map[secid] = yields_dict
            
            # Объединяем данные
            for row in sec_data:
                bond_dict = dict(zip(sec_columns, row))
                
                # Пропускаем облигации с режимом торгов SPOB
                boardid = bond_dict.get("BOARDID")
                if boardid and boardid.strip().upper() == "SPOB":
                    continue
                
                secid = bond_dict.get("SECID")
                if not secid:
                    continue
                
                # Сохраняем BONDTYPE из bonds.json как BONDTYPE43 ДО того, как оно будет перезаписано
                # значением из bonds_emitent.json
                if "BONDTYPE" in bond_dict:
                    bondtype43_value = bond_dict.get("BONDTYPE")
                    if bondtype43_value:
                        bond_dict["BONDTYPE43"] = bondtype43_value.strip() if isinstance(bondtype43_value, str) else bondtype43_value
                        self.logger.debug(f"Сохранено BONDTYPE43='{bond_dict['BONDTYPE43']}' для облигации {secid}")
                else:
                    self.logger.debug(f"Поле BONDTYPE отсутствует в bonds.json для облигации {secid}")
                
                # Добавляем данные из marketdata
                if secid in marketdata_map:
                    bond_dict.update(marketdata_map[secid])
                
                # Добавляем данные из yields
                if secid in yields_map:
                    bond_dict.update(yields_map[secid])
                
                bonds_data.append(bond_dict)
            
            self.logger.debug(f"Загружено {len(bonds_data)} облигаций из bonds.json")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке bonds.json: {e}", exc_info=True)
            return bonds_data
        
        # Загружаем рейтинги
        ratings_map = self._load_ratings_map()
        for bond in bonds_data:
            secid = bond.get("SECID")
            if secid and secid in ratings_map:
                bond["RATINGS"] = ratings_map[secid].get("all_ratings", [])
                worst_rating = self._get_worst_rating(bond["RATINGS"])
                if worst_rating:
                    bond["RATING_AGENCY"] = worst_rating.get("agency_name_short_ru", "").strip()
                    rating_level_raw = worst_rating.get("rating_level_name_short_ru", "").strip()
                    # Стандартизируем рейтинг: удаляем русские индикаторы рынка
                    bond["RATING_LEVEL"] = standardize_rating(rating_level_raw) or rating_level_raw
        
        # Загружаем типы облигаций из bonds_emitent.json
        emitent_map = self._load_emitent_map()
        for bond in bonds_data:
            secid = bond.get("SECID")
            if secid and secid in emitent_map:
                bond["BONDTYPE"] = emitent_map[secid].get("type")
                # Добавляем рейтинги эмитента, если рейтингов облигации нет
                if "RATINGS" not in bond or not bond.get("RATINGS"):
                    emitent_ratings = emitent_map[secid].get("cci_rating_companies", [])
                    if emitent_ratings:
                        bond["RATINGS"] = emitent_ratings
        
        # Загружаем данные о купонах
        coupons_map = self._load_coupons_map()
        for bond in bonds_data:
            secid = bond.get("SECID")
            if secid and secid in coupons_map:
                bond_data = coupons_map[secid]
                coupons = bond_data.get("coupons", [])
                if coupons:
                    # Берём значение купона из ближайшего купона
                    coupon_loader = get_coupon_loader()
                    if coupon_loader:
                        coupon_value = coupon_loader.get_nearest_coupon_value(secid)
                        if coupon_value is not None:
                            bond["COUPONVALUE"] = coupon_value
        
        return bonds_data
    
    def _load_ratings_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает рейтинги из bonds_rating.json"""
        ratings_map = {}
        ratings_path = self.data_dir / "bonds_rating.json"
        
        if not ratings_path.exists():
            return ratings_map
        
        try:
            with open(ratings_path, 'rb') as f:
                ratings_data = orjson.loads(f.read())
            
            for secid, rating_entry in ratings_data.items():
                if isinstance(rating_entry, dict):
                    ratings_list = rating_entry.get("ratings", [])
                    if not ratings_list:
                        ratings_list = rating_entry.get("all_ratings", [])
                elif isinstance(rating_entry, list):
                    ratings_list = rating_entry
                else:
                    continue
                
                if isinstance(ratings_list, list) and len(ratings_list) > 0:
                    valid_ratings = [
                        r for r in ratings_list 
                        if isinstance(r, dict) and r.get("agency_name_short_ru", "").strip()
                    ]
                    if valid_ratings:
                        ratings_map[secid] = {"all_ratings": valid_ratings}
        except Exception as e:
            self.logger.warning(f"Ошибка при загрузке рейтингов: {e}")
        
        return ratings_map
    
    def _load_emitent_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные эмитентов из bonds_emitent.json"""
        emitent_map = {}
        emitent_path = self.data_dir / "bonds_emitent.json"
        
        if not emitent_path.exists():
            return emitent_map
        
        try:
            with open(emitent_path, 'rb') as f:
                emitent_data = orjson.loads(f.read())
            
            for secid, emitent_entry in emitent_data.items():
                if isinstance(emitent_entry, dict):
                    emitent_map[secid] = emitent_entry
        except Exception as e:
            self.logger.warning(f"Ошибка при загрузке данных эмитентов: {e}")
        
        return emitent_map
    
    def _load_coupons_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные о купонах из coupons_data.json"""
        coupons_map = {}
        coupons_path = self.data_dir / "coupons_data.json"
        
        if not coupons_path.exists():
            return coupons_map
        
        try:
            with open(coupons_path, 'rb') as f:
                coupons_data = orjson.loads(f.read())
            
            bonds_data = coupons_data.get("bonds", {})
            for secid, bond_data in bonds_data.items():
                if isinstance(bond_data, dict):
                    coupons_map[secid] = bond_data
        except Exception as e:
            self.logger.warning(f"Ошибка при загрузке данных о купонах: {e}")
        
        return coupons_map
    
    def _calculate_coupon_frequency(self, coupon_period: Optional[int]) -> Optional[float]:
        """
        Вычисляет частоту купона (число выплат в год).
        
        Args:
            coupon_period: Период купона в днях
        
        Returns:
            Частота купона (округлённая до целого) или None
        """
        if coupon_period is None or coupon_period == 0:
            return None
        
        try:
            frequency = 365 / coupon_period
            return round(frequency)
        except (ZeroDivisionError, TypeError):
            return None
    
    def _get_worst_rating(self, ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Определяет наихудший рейтинг из списка рейтингов.
        
        Args:
            ratings_list: Список словарей с рейтингами
        
        Returns:
            Словарь с наихудшим рейтингом или None
        """
        if not ratings_list:
            return None
        
        # Фильтруем рейтинги со значением "Отозван"
        non_revoked_ratings = [
            r for r in ratings_list
            if isinstance(r, dict) and r.get("rating_level_name_short_ru", "").lower() not in ["отозван", "отозвано"]
        ]
        
        # Если есть неотозванные рейтинги, используем их, иначе все рейтинги
        ratings_to_check = non_revoked_ratings if non_revoked_ratings else ratings_list
        
        if not ratings_to_check:
            return None
        
        # Находим наихудший рейтинг (наибольший индекс в шкале)
        worst_rating = None
        worst_index = -1
        
        for rating in ratings_to_check:
            rating_level = rating.get("rating_level_name_short_ru", "")
            if not rating_level:
                continue
            
            rating_index = get_rating_index(rating_level)
            if rating_index is not None and rating_index > worst_index:
                worst_index = rating_index
                worst_rating = rating
        
        return worst_rating
    
    def _get_bond_rating(self, bond_data: Dict[str, Any], emitent_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Получает итоговый рейтинг облигации и стандартизирует его.
        
        Args:
            bond_data: Данные облигации
            emitent_data: Данные эмитента (опционально)
        
        Returns:
            Стандартизированная строка с рейтингом (например, "AAA", "AA+") или None.
            Все русские индикаторы рынка ((RU), .ru, ru префикс) удаляются.
        """
        # Сначала пытаемся получить рейтинг из данных облигации
        ratings = bond_data.get("RATINGS", [])
        
        # Если рейтинга нет, пытаемся получить из данных эмитента
        if not ratings and emitent_data:
            ratings = emitent_data.get("cci_rating_companies", [])
            # Если это список словарей, используем его напрямую
            if not isinstance(ratings, list):
                ratings = []
        
        if not ratings:
            return None
        
        worst_rating = self._get_worst_rating(ratings)
        if worst_rating:
            rating_str = worst_rating.get("rating_level_name_short_ru", "").strip()
            if rating_str:
                # Стандартизируем рейтинг: удаляем русские индикаторы рынка
                standardized = standardize_rating(rating_str)
                return standardized
        
        return None
    
    def _transform_bond_data(self, raw_data: Dict[str, Any], type_mapping: Dict[str, int], kind_mapping: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Преобразует данные из JSON в формат таблицы.
        
        Args:
            raw_data: Сырые данные облигации из JSON
            type_mapping: Маппинг типов облигаций
            kind_mapping: Маппинг видов облигаций
        
        Returns:
            Словарь с преобразованными данными или None
        """
        secid = raw_data.get("SECID")
        if not secid:
            return None
        
        # Получаем данные эмитента для рейтинга
        emitent_service = get_emitent_service()
        emitent_data = emitent_service.get_emitent_by_secid(secid) if emitent_service else None
        
        # Получаем рейтинг
        rating = self._get_bond_rating(raw_data, emitent_data)
        
        # Вычисляем coupon_frequency
        coupon_period = raw_data.get("COUPONPERIOD")
        coupon_frequency = self._calculate_coupon_frequency(coupon_period)
        
        # Вычисляем duration_years
        duration = raw_data.get("DURATION")
        duration_years = None
        if duration is not None:
            try:
                duration_years = round(duration / 365, 2)
            except (TypeError, ZeroDivisionError):
                duration_years = None
        
        # Определяем has_put_option и has_call_option
        has_put_option = 1 if raw_data.get("PUTOPTIONDATE") else 0
        has_call_option = 1 if raw_data.get("CALLOPTIONDATE") else 0
        
        # Получаем текущую цену (PREVPRICE или PREVWAPRICE)
        current_price = raw_data.get("PREVPRICE") or raw_data.get("PREVWAPRICE")
        
        # Получаем yield_to_maturity
        yield_to_maturity = raw_data.get("YIELDATPREVWAPRICE")
        
        # Вычисляем coupon_yield_to_price
        coupon_yield_to_price = None
        coupon_value = raw_data.get("COUPONVALUE")
        face_value = raw_data.get("FACEVALUE")
        if coupon_value is not None and current_price is not None and face_value is not None and coupon_period and coupon_period > 0:
            try:
                payments_per_year = 365 / coupon_period
                if current_price > 0 and face_value > 0:
                    coupon_yield_to_price = (coupon_value * 10000 / (current_price * face_value)) * payments_per_year
            except (ZeroDivisionError, TypeError):
                pass
        
        # Получаем bond_type из маппинга
        bond_type = None
        bond_type_str = raw_data.get("BONDTYPE")
        if bond_type_str and bond_type_str in type_mapping:
            bond_type = type_mapping[bond_type_str]
        
        # Получаем bond_kind из маппинга
        bond_kind = None
        bond_kind_str = raw_data.get("BONDTYPE43")
        if bond_kind_str:
            # Убираем лишние пробелы для точного совпадения
            bond_kind_str = bond_kind_str.strip()
            if bond_kind_str in kind_mapping:
                bond_kind = kind_mapping[bond_kind_str]
            else:
                self.logger.debug(f"BONDTYPE43 '{bond_kind_str}' не найден в маппинге для облигации {secid}")
        else:
            self.logger.debug(f"BONDTYPE43 отсутствует для облигации {secid}")
        
        # Форматируем даты
        def format_date(date_value):
            if date_value is None:
                return None
            if isinstance(date_value, date):
                return date_value.strftime("%Y-%m-%d")
            if isinstance(date_value, str):
                # Проверяем, что это валидная дата
                if date_value and date_value != "0000-00-00":
                    return date_value
                return None
            return None
        
        maturity_date = format_date(raw_data.get("MATDATE"))
        offer_date = format_date(raw_data.get("OFFERDATE"))
        
        # Формируем итоговый словарь
        # В столбец name сохраняем SHORTNAME из bonds.json (краткое наименование)
        transformed = {
            "secid": secid,
            "boardid": raw_data.get("BOARDID"),
            "isin": raw_data.get("ISIN"),
            "name": raw_data.get("SHORTNAME") or raw_data.get("SECNAME"),
            "rating": rating,
            "current_price": current_price,
            "coupon_yield_to_price": coupon_yield_to_price,
            "yield_to_maturity": yield_to_maturity,
            "face_value": raw_data.get("FACEVALUE"),
            "currency": raw_data.get("FACEUNIT"),
            "coupon_value": coupon_value,
            "coupon_percent": raw_data.get("COUPONPERCENT"),
            "coupon_frequency": coupon_frequency,
            "accrued_interest": raw_data.get("ACCRUEDINT"),
            "duration_years": duration_years,
            "has_put_option": has_put_option,
            "has_call_option": has_call_option,
            "maturity_date": maturity_date,
            "listing_level": raw_data.get("LISTLEVEL"),
            "bond_type": bond_type,
            "bond_kind": bond_kind,
            "offer_date": offer_date,
        }
        
        return transformed
    
    def _insert_or_replace_bonds(self, bonds: List[Dict[str, Any]]) -> None:
        """
        Вставляет или заменяет записи в таблице bonds.
        
        Args:
            bonds: Список словарей с данными облигаций
        """
        if not bonds:
            self.logger.warning("Нет данных для вставки")
            return
        
        insert_sql = """
        INSERT OR REPLACE INTO bonds (
            secid, boardid, isin, name, rating, current_price, coupon_yield_to_price,
            yield_to_maturity, face_value, currency, coupon_value, coupon_percent,
            coupon_frequency, accrued_interest, duration_years, has_put_option,
            has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                inserted_count = 0
                for bond in bonds:
                    cursor.execute(insert_sql, (
                        bond.get("secid"),
                        bond.get("boardid"),
                        bond.get("isin"),
                        bond.get("name"),
                        bond.get("rating"),
                        bond.get("current_price"),
                        bond.get("coupon_yield_to_price"),
                        bond.get("yield_to_maturity"),
                        bond.get("face_value"),
                        bond.get("currency"),
                        bond.get("coupon_value"),
                        bond.get("coupon_percent"),
                        bond.get("coupon_frequency"),
                        bond.get("accrued_interest"),
                        bond.get("duration_years"),
                        bond.get("has_put_option"),
                        bond.get("has_call_option"),
                        bond.get("maturity_date"),
                        bond.get("listing_level"),
                        bond.get("bond_type"),
                        bond.get("bond_kind"),
                        bond.get("offer_date"),
                    ))
                    inserted_count += 1
                
                # Фиксируем транзакцию (SQLite автоматически начинает транзакцию)
                conn.commit()
                self.logger.info(f"Успешно вставлено/обновлено {inserted_count} записей в таблицу bonds")
        except Exception as e:
            self.logger.error(f"Ошибка при вставке данных в таблицу bonds: {e}", exc_info=True)
            raise

    # -------------------------------------------------------------------------
    # Слой данных: только SQL-запросы, возврат сырых данных (list of dict).
    # Фильтрация по рейтингу теперь выполняется на уровне БД в методе select().
    # Фильтрация по эмитенту выполняется в сервисном слое (требует дополнительных данных).
    # -------------------------------------------------------------------------

    def select(
        self,
        filters: Optional[BondFilters] = None,
        *,
        # Прямые параметры для обратной совместимости
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
    ) -> List[Dict[str, Any]]:
        """
        Универсальный метод для выборки облигаций с динамическим формированием SQL-запроса.
        
        Применяет все фильтры на уровне базы данных для повышения производительности.
        Особое внимание уделено фильтрации по рейтингу, которая реализована через SQL-условия
        с учетом шкалы RATINGS и возможных префиксов/суффиксов в значениях рейтингов.
        
        Args:
            filters: Объект BondFilters с параметрами фильтрации (приоритет над прямыми параметрами)
            coupon_percent_min: Минимальный процент купона
            coupon_percent_max: Максимальный процент купона
            yield_to_maturity_min: Минимальная доходность к погашению
            yield_to_maturity_max: Максимальная доходность к погашению
            coupon_yield_to_price_min: Минимальная доходность купона к цене
            coupon_yield_to_price_max: Максимальная доходность купона к цене
            maturity_date_from: Дата погашения от (YYYY-MM-DD)
            maturity_date_to: Дата погашения до (YYYY-MM-DD)
            listlevel: Список уровней листинга
            currency: Список валют
            bond_type_ids: Список ID типов облигаций
            bond_kind_ids: Список ID видов облигаций
            rating_min: Минимальный рейтинг (из шкалы RATINGS)
            rating_max: Максимальный рейтинг (из шкалы RATINGS)
            exclude_spob: Исключить облигации с режимом торгов SPOB
        
        Returns:
            Список словарей с данными облигаций. Каждый словарь содержит все поля таблицы bonds.
            Если таблица не существует, возвращает пустой список.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        if not self._table_exists("bonds"):
            self.logger.warning("Таблица bonds не существует, select возвращает []")
            return []
        
        # Используем фильтры из объекта, если передан, иначе используем прямые параметры
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
        
        # Формируем динамические WHERE-условия
        where_parts: List[str] = []
        params: List[Any] = []
        
        # Фильтр по проценту купона (диапазон)
        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        
        # Фильтр по доходности к погашению (диапазон)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        
        # Фильтр по доходности купона к цене (диапазон)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        
        # Фильтр по дате погашения (диапазон)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        
        # Фильтр по уровню листинга (IN)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        
        # Фильтр по валюте (IN)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        
        # Фильтр по типу облигации (IN)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        
        # Фильтр по виду облигации (IN)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        
        # Фильтр по рейтингу (специальная логика с учетом шкалы RATINGS)
        # Использует оператор IN с динамическим списком рейтингов из диапазона
        if rating_min is not None or rating_max is not None:
            rating_result = self._build_rating_filter_sql(rating_min, rating_max)
            if rating_result:
                # rating_result - это кортеж (SQL-условие, список параметров)
                rating_sql, rating_params = rating_result
                where_parts.append(rating_sql)
                params.extend(rating_params)
        
        # Фильтр по режиму торгов SPOB
        if exclude_spob:
            if self._column_exists("bonds", "boardid"):
                where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")
        
        # Формируем финальный SQL-запрос
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        
        # Определяем список колонок с учетом наличия boardid
        base_cols = "secid, isin, name, rating, current_price, coupon_yield_to_price, yield_to_maturity, face_value, currency, coupon_value, coupon_percent, coupon_frequency, accrued_interest, duration_years, has_put_option, has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date"
        if self._column_exists("bonds", "boardid"):
            base_cols = "secid, boardid, isin, name, rating, current_price, coupon_yield_to_price, yield_to_maturity, face_value, currency, coupon_value, coupon_percent, coupon_frequency, accrued_interest, duration_years, has_put_option, has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date"
        
        sql = f"SELECT {base_cols} FROM bonds WHERE {where_sql}"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                self.logger.debug(f"Выбрано {len(result)} записей из таблицы bonds с применением фильтров")
                return result
        except Exception as e:
            self.logger.error(f"Ошибка при select: {e}", exc_info=True)
            raise
    
    def _build_rating_filter_sql(
        self,
        rating_min: Optional[str],
        rating_max: Optional[str]
    ) -> Optional[Tuple[str, List[str]]]:
        """
        Формирует SQL-условие для фильтрации по рейтингу с использованием оператора IN.
        
        Использует константу RATINGS_ORDER для определения диапазона рейтингов.
        Правильно обрабатывает случай, когда rating_min может быть больше rating_max
        (пользователь может выбрать диапазон в любом порядке).
        
        Args:
            rating_min: Один из граничных рейтингов (может быть как минимальным, так и максимальным)
            rating_max: Другой граничный рейтинг (может быть как минимальным, так и максимальным)
        
        Returns:
            Кортеж (SQL-строка с условием для WHERE, список параметров) или None, если фильтр не применим.
            Список параметров содержит рейтинги из диапазона для оператора IN.
        """
        # Если оба фильтра None, фильтр не применяется
        if rating_min is None and rating_max is None:
            return None
        
        # Определяем индексы границ диапазона в RATINGS_ORDER
        try:
            idx_start = RATINGS_ORDER.index(rating_min.upper()) if rating_min is not None else 0
            idx_end = RATINGS_ORDER.index(rating_max.upper()) if rating_max is not None else len(RATINGS_ORDER) - 1
        except ValueError:
            # Если рейтинг не найден в шкале, не применяем фильтр
            self.logger.warning(f"Рейтинг не найден в шкале RATINGS_ORDER: min={rating_min}, max={rating_max}")
            return None
        
        # Срезаем список (всегда берем от меньшего индекса к большему)
        # Это позволяет корректно обработать случай, когда пользователь выбрал диапазон
        # в обратном порядке (например, от AA- до AA вместо от AA до AA-)
        low = min(idx_start, idx_end)
        high = max(idx_start, idx_end)
        
        # Формируем список рейтингов в диапазоне [low, high] включительно
        ratings_in_range = RATINGS_ORDER[low:high + 1]
        
        if not ratings_in_range:
            return None
        
        # В таблице рейтинги хранятся без префиксов и суффиксов (просто 'AAA', 'AA+', 'AA', и т.д.)
        # Поэтому используем только базовые значения рейтингов
        # Формируем SQL-условие с использованием IN
        # Используем UPPER для case-insensitive сравнения
        # Исключаем NULL и пустые строки
        placeholders = ",".join("?" * len(ratings_in_range))
        sql_condition = f"(rating IS NOT NULL AND TRIM(rating) != '' AND UPPER(TRIM(rating)) IN ({placeholders}))"
        
        # Возвращаем условие и список рейтингов (в верхнем регистре для сравнения)
        rating_params = [rating.upper() for rating in ratings_in_range]
        return (sql_condition, rating_params)

    def fetch_bonds_raw(
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
        exclude_spob: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Выполняет SELECT по таблице bonds с учётом переданных фильтров.
        Возвращает сырые строки в виде списка словарей (ключи — имена колонок).

        Не выполняет фильтрацию по рейтингу и эмитенту — это зона ответственности
        сервисного слоя.
        """
        if not self._table_exists("bonds"):
            self.logger.warning("Таблица bonds не существует, fetch_bonds_raw возвращает []")
            return []

        where_parts: List[str] = []
        params: List[Any] = []

        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        if exclude_spob:
            # boardid может отсутствовать в старых схемах; тогда фильтр не применяем
            if self._column_exists("bonds", "boardid"):
                where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        base_cols = "secid, isin, name, rating, current_price, coupon_yield_to_price, yield_to_maturity, face_value, currency, coupon_value, coupon_percent, coupon_frequency, accrued_interest, duration_years, has_put_option, has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date"
        if self._column_exists("bonds", "boardid"):
            base_cols = "secid, boardid, isin, name, rating, current_price, coupon_yield_to_price, yield_to_maturity, face_value, currency, coupon_value, coupon_percent, coupon_frequency, accrued_interest, duration_years, has_put_option, has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date"
        sql = f"SELECT {base_cols} FROM bonds WHERE {where_sql}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Ошибка при fetch_bonds_raw: {e}", exc_info=True)
            raise

    def count(
        self,
        filters: Optional[BondFilters] = None,
        *,
        # Прямые параметры для обратной совместимости
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
        """
        Универсальный метод для подсчета облигаций с применением всех фильтров на уровне БД.
        
        Использует ту же логику фильтрации, что и метод select, но возвращает только количество записей.
        
        Args:
            filters: Объект BondFilters с параметрами фильтрации (приоритет над прямыми параметрами)
            ... (остальные параметры аналогичны методу select)
        
        Returns:
            Количество облигаций, соответствующих фильтрам
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        if not self._table_exists("bonds"):
            return 0
        
        # Используем фильтры из объекта, если передан, иначе используем прямые параметры
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
        
        # Формируем динамические WHERE-условия (та же логика, что и в select)
        where_parts: List[str] = []
        params: List[Any] = []
        
        # Применяем те же фильтры, что и в методе select
        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        
        # Фильтр по рейтингу (используем ту же логику, что и в select)
        if rating_min is not None or rating_max is not None:
            rating_result = self._build_rating_filter_sql(rating_min, rating_max)
            if rating_result:
                # rating_result - это кортеж (SQL-условие, список параметров)
                rating_sql, rating_params = rating_result
                where_parts.append(rating_sql)
                params.extend(rating_params)
        
        if exclude_spob:
            if self._column_exists("bonds", "boardid"):
                where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")
        
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        sql = f"SELECT COUNT(*) FROM bonds WHERE {where_sql}"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return int(cursor.fetchone()[0])
        except Exception as e:
            self.logger.error(f"Ошибка при count: {e}", exc_info=True)
            raise

    def count_bonds(
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
        exclude_spob: bool = False,
    ) -> int:
        """
        Возвращает количество записей в bonds с учётом тех же фильтров, что и
        fetch_bonds_raw. Используется для total/filtered в ответе API.
        """
        if not self._table_exists("bonds"):
            return 0

        where_parts: List[str] = []
        params: List[Any] = []

        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        if exclude_spob:
            if self._column_exists("bonds", "boardid"):
                where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        sql = f"SELECT COUNT(*) FROM bonds WHERE {where_sql}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return int(cursor.fetchone()[0])
        except Exception as e:
            self.logger.error(f"Ошибка при count_bonds: {e}", exc_info=True)
            raise


class DBCoupon:
    """
    Слой данных: работа с БД купонов облигаций.
    
    - refresh(): создание/обновление таблицы coupons из JSON (миграции).
    Обеспечивает полную синхронизацию данных купонов облигаций между JSON-источниками
    и SQLite базой данных с гарантией целостности и актуальности информации.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Инициализация сервиса
        
        Args:
            db_path: Путь к файлу базы данных. Если не указан, используется backend/db/bonds.db
        """
        if db_path is None:
            # Определяем путь относительно текущего файла
            backend_dir = Path(__file__).parent.parent.parent
            db_path = str(backend_dir / "db" / "bonds.db")
        
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
    
    def refresh(self, table_name: str) -> None:
        """
        Главный метод синхронизации данных купонов облигаций.
        
        Последовательность выполнения:
        1. Установить соединение с базой данных
        2. Проверить существование таблицы coupons
        3. Если таблица не существует — создать её
        4. Загрузить данные из coupons_data.json
        5. Преобразовать данные для каждой записи
        6. Выполнить INSERT OR REPLACE INTO для всех записей в транзакции
        7. Зафиксировать транзакцию
        8. При ошибке выполнить rollback и пробросить исключение
        
        Args:
            table_name: Имя таблицы для работы в БД (должно быть "coupons")
        
        Raises:
            FileNotFoundError: Если JSON файл не найден
            orjson.JSONDecodeError: Если JSON файл некорректен
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        try:
            # Создаём директорию для БД, если она не существует
            self._ensure_db_directory()
            
            # Устанавливаем соединение с базой данных
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем существование таблицы
                if not self._table_exists(table_name):
                    self.logger.info(f"Таблица {table_name} не существует, создаём её")
                    self._create_coupons_table(conn)
                else:
                    self.logger.info(f"Таблица {table_name} существует, обновляем данные")
                
                # Загружаем данные из JSON
                coupons_data = self._load_json_data()
                if not coupons_data:
                    self.logger.warning("JSON файл пуст или не содержит данных о купонах")
                    return
                
                self.logger.info(f"Загружено {len(coupons_data)} записей купонов из JSON-файла")
                
                # Преобразуем данные
                transformed_coupons = []
                for raw_coupon in coupons_data:
                    try:
                        transformed = self._transform_coupon_data(raw_coupon)
                        if transformed:
                            transformed_coupons.append(transformed)
                    except Exception as e:
                        self.logger.warning(
                            f"Ошибка при преобразовании данных купона "
                            f"(secid={raw_coupon.get('secid', 'unknown')}, "
                            f"coupondate={raw_coupon.get('coupondate', 'unknown')}): {e}"
                        )
                        continue
                
                self.logger.info(f"Преобразовано {len(transformed_coupons)} записей купонов")
                
                # Вставляем или заменяем записи в транзакции
                self._insert_or_replace_coupons(conn, transformed_coupons)
                
                self.logger.info(
                    f"Таблица {table_name} успешно создана/обновлена в базе данных: {self.db_path}"
                )
        except (FileNotFoundError, orjson.JSONDecodeError) as e:
            self.logger.error(f"Ошибка при загрузке данных из JSON: {str(e)}", exc_info=True)
            raise
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при работе с базой данных: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при синхронизации купонов: {str(e)}", exc_info=True)
            raise
    
    def _ensure_db_directory(self) -> None:
        """Создает директорию для базы данных, если она не существует"""
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Директория для БД проверена/создана: {db_dir}")
    
    def _table_exists(self, table_name: str) -> bool:
        """
        Проверяет существование таблицы в базе данных через запрос к sqlite_master.
        
        Args:
            table_name: Имя таблицы для проверки
        
        Returns:
            True если таблица существует, False в противном случае
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Ошибка при проверке существования таблицы: {e}")
            return False
    
    def _create_coupons_table(self, conn: sqlite3.Connection) -> None:
        """
        Создает таблицу coupons с указанной структурой.
        
        Args:
            conn: Соединение с базой данных
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS coupons (
            secid TEXT NOT NULL,
            coupondate TEXT,
            recorddate TEXT,
            startdate TEXT,
            initialfacevalue INTEGER,
            facevalue INTEGER,
            faceunit TEXT,
            value REAL,
            valueprc REAL,
            value_rub REAL,
            PRIMARY KEY (secid, coupondate)
        )
        """
        
        try:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            self.logger.info("Таблица coupons успешно создана")
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при создании таблицы coupons: {e}", exc_info=True)
            raise
    
    def _load_json_data(self) -> list:
        """
        Загружает данные из coupons_data.json.
        
        Returns:
            Список словарей с данными купонов, где каждый словарь содержит secid и данные купона
        
        Raises:
            FileNotFoundError: Если файл не найден
            orjson.JSONDecodeError: Если JSON некорректен
        """
        # Определяем путь к файлу относительно текущего файла
        backend_dir = Path(__file__).parent.parent.parent
        data_dir = backend_dir / "app" / "data"
        coupons_path = data_dir / "coupons_data.json"
        
        if not coupons_path.exists():
            error_msg = f"Файл coupons_data.json не найден: {coupons_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(coupons_path, 'rb') as f:
                data = orjson.loads(f.read())
            
            # Извлекаем данные о купонах из структуры {"bonds": {"SECID": {"coupons": [...]}}}
            bonds_data = data.get("bonds", {})
            coupons_list = []
            
            for secid, bond_data in bonds_data.items():
                if not isinstance(bond_data, dict):
                    continue
                
                coupons = bond_data.get("coupons", [])
                if not isinstance(coupons, list):
                    continue
                
                # Добавляем secid к каждому купону
                for coupon in coupons:
                    if isinstance(coupon, dict):
                        coupon_with_secid = coupon.copy()
                        coupon_with_secid["secid"] = secid
                        coupons_list.append(coupon_with_secid)
            
            return coupons_list
        except orjson.JSONDecodeError as e:
            error_msg = f"Ошибка при декодировании JSON файла {coupons_path}: {e}"
            self.logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Ошибка при загрузке данных из {coupons_path}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise
    
    def _transform_coupon_data(self, raw_data: dict) -> dict:
        """
        Преобразует JSON данные в формат таблицы с обработкой отсутствующих полей.
        
        При отсутствии полей в JSON:
        - Для текстовых полей используется None (NULL)
        - Для числовых полей используется 0
        
        Args:
            raw_data: Словарь с сырыми данными купона из JSON
        
        Returns:
            Словарь с преобразованными данными для вставки в таблицу
        """
        # Извлекаем обязательные поля для составного ключа
        secid = raw_data.get("secid")
        coupondate = raw_data.get("coupondate")
        
        if not secid or not coupondate:
            self.logger.warning(
                f"Пропущена запись купона: отсутствует secid или coupondate. "
                f"Данные: {raw_data}"
            )
            return None
        
        # Преобразуем данные с обработкой отсутствующих полей
        transformed = {
            "secid": secid,
            "coupondate": coupondate if coupondate else None,
            "recorddate": raw_data.get("recorddate") if raw_data.get("recorddate") else None,
            "startdate": raw_data.get("startdate") if raw_data.get("startdate") else None,
            "initialfacevalue": raw_data.get("initialfacevalue") if raw_data.get("initialfacevalue") is not None else 0,
            "facevalue": raw_data.get("facevalue") if raw_data.get("facevalue") is not None else 0,
            "faceunit": raw_data.get("faceunit") if raw_data.get("faceunit") else None,
            "value": raw_data.get("value") if raw_data.get("value") is not None else 0.0,
            "valueprc": raw_data.get("valueprc") if raw_data.get("valueprc") is not None else 0.0,
            "value_rub": raw_data.get("value_rub") if raw_data.get("value_rub") is not None else 0.0,
        }
        
        return transformed
    
    def _insert_or_replace_coupons(self, conn: sqlite3.Connection, coupons: list) -> None:
        """
        Вставляет или заменяет записи используя INSERT OR REPLACE INTO.
        
        Все операции выполняются в рамках одной транзакции с явным commit или rollback
        при ошибках.
        
        Args:
            conn: Соединение с базой данных
            coupons: Список словарей с данными купонов для вставки/обновления
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        if not coupons:
            self.logger.warning("Нет данных для вставки")
            return
        
        insert_sql = """
        INSERT OR REPLACE INTO coupons (
            secid, coupondate, recorddate, startdate, initialfacevalue,
            facevalue, faceunit, value, valueprc, value_rub
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            cursor = conn.cursor()
            inserted_count = 0
            
            for coupon in coupons:
                cursor.execute(insert_sql, (
                    coupon.get("secid"),
                    coupon.get("coupondate"),
                    coupon.get("recorddate"),
                    coupon.get("startdate"),
                    coupon.get("initialfacevalue"),
                    coupon.get("facevalue"),
                    coupon.get("faceunit"),
                    coupon.get("value"),
                    coupon.get("valueprc"),
                    coupon.get("value_rub"),
                ))
                inserted_count += 1
            
            # Фиксируем транзакцию
            conn.commit()
            self.logger.info(f"Успешно вставлено/обновлено {inserted_count} записей в таблицу coupons")
        except sqlite3.Error as e:
            # Выполняем rollback при ошибке
            conn.rollback()
            self.logger.error(f"Ошибка при вставке данных в таблицу coupons: {e}", exc_info=True)
            raise
    
    def fetch_coupons_raw(self, secids: List[str]) -> List[Dict[str, Any]]:
        """
        Выполняет SELECT по таблице coupons для указанных secid.
        Возвращает сырые строки в виде списка словарей (ключи — имена колонок).
        
        Args:
            secids: Список идентификаторов облигаций (secid) для выборки купонов
        
        Returns:
            Список словарей с данными купонов. Каждый словарь содержит все поля таблицы coupons.
            Если таблица не существует или список secids пуст, возвращает пустой список.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        if not secids:
            self.logger.warning("Список secids пуст, fetch_coupons_raw возвращает []")
            return []
        
        if not self._table_exists("coupons"):
            self.logger.warning("Таблица coupons не существует, fetch_coupons_raw возвращает []")
            return []
        
        # Формируем SQL запрос с IN для фильтрации по secid
        placeholders = ",".join("?" * len(secids))
        sql = f"""
        SELECT 
            secid, coupondate, recorddate, startdate, initialfacevalue,
            facevalue, faceunit, value, valueprc, value_rub
        FROM coupons 
        WHERE secid IN ({placeholders})
        ORDER BY secid, coupondate
        """
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, secids)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                self.logger.debug(f"Выбрано {len(result)} записей купонов для {len(secids)} облигаций")
                return result
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при fetch_coupons_raw: {e}", exc_info=True)
            raise


class DBkbd:
    """
    Слой данных: работа с БД кривой бескупонной доходности (KBD).
    
    - refresh(): создание/обновление таблицы kbd из CSV (миграции).
    - get_kbd_data(): извлечение сырых данных из таблицы kbd.
    Обеспечивает полную синхронизацию данных кривой бескупонной доходности между CSV-источником
    и SQLite базой данных с гарантией целостности и актуальности информации.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Инициализация сервиса
        
        Args:
            db_path: Путь к файлу базы данных. Если не указан, используется backend/db/bonds.db
        """
        if db_path is None:
            # Определяем путь относительно текущего файла
            backend_dir = Path(__file__).parent.parent.parent
            db_path = str(backend_dir / "db" / "bonds.db")
        
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
        # Маппинг русских заголовков на английские столбцы
        self.column_mapping = {
            "Дата": "date",
            "Время": "time",
            "Срок 0.25 лет": "term_0_25",
            "Срок 0.5 лет": "term_0_5",
            "Срок 0.75 лет": "term_0_75",
            "Срок 1.0 лет": "term_1_0",
            "Срок 2.0 лет": "term_2_0",
            "Срок 3.0 лет": "term_3_0",
            "Срок 5.0 лет": "term_5_0",
            "Срок 7.0 лет": "term_7_0",
            "Срок 10.0 лет": "term_10_0",
            "Срок 15.0 лет": "term_15_0",
            "Срок 20.0 лет": "term_20_0",
            "Срок 30.0 лет": "term_30_0"
        }
    
    def refresh(self, table_name: str) -> None:
        """
        Главный метод синхронизации данных кривой бескупонной доходности.
        
        Последовательность выполнения:
        1. Установить соединение с базой данных
        2. Проверить существование таблицы kbd
        3. Если таблица не существует — создать её
        4. Загрузить данные из backend/data/zerocupon.csv
        5. Преобразовать данные для каждой записи
        6. Выполнить INSERT OR REPLACE INTO для всех записей в транзакции
        7. Зафиксировать транзакцию
        8. При ошибке выполнить rollback и пробросить исключение
        
        Args:
            table_name: Имя таблицы для работы в БД (должно быть "kbd")
        
        Raises:
            FileNotFoundError: Если CSV файл не найден
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        try:
            # Создаём директорию для БД, если она не существует
            self._ensure_db_directory()
            
            # Устанавливаем соединение с базой данных
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем существование таблицы
                if not self._table_exists(table_name):
                    self.logger.info(f"Таблица {table_name} не существует, создаём её")
                    self._create_kbd_table(conn)
                else:
                    self.logger.info(f"Таблица {table_name} существует, обновляем данные")
                
                # Загружаем данные из CSV
                raw_data = self._load_csv_data()
                if not raw_data:
                    self.logger.warning("CSV файл пуст или не содержит данных")
                    return
                
                self.logger.info(f"Загружено {len(raw_data)} записей из CSV-файла")
                
                # Преобразуем данные
                transformed_records = []
                for raw_record in raw_data:
                    try:
                        transformed = self._transform_kbd_data(raw_record)
                        if transformed:
                            transformed_records.append(transformed)
                    except Exception as e:
                        self.logger.warning(
                            f"Ошибка при преобразовании данных KBD "
                            f"(date={raw_record.get('Дата', 'unknown')}, "
                            f"time={raw_record.get('Время', 'unknown')}): {e}"
                        )
                        continue
                
                self.logger.info(f"Преобразовано {len(transformed_records)} записей")
                
                # Вставляем или заменяем записи в транзакции
                self._insert_or_replace_kbd(conn, transformed_records)
                
                self.logger.info(
                    f"Таблица {table_name} успешно создана/обновлена в базе данных: {self.db_path}"
                )
        except FileNotFoundError as e:
            self.logger.error(f"Ошибка при загрузке данных из CSV: {str(e)}", exc_info=True)
            raise
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при работе с базой данных: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при синхронизации KBD: {str(e)}", exc_info=True)
            raise
    
    def _ensure_db_directory(self) -> None:
        """Создает директорию для базы данных, если она не существует"""
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Директория для БД проверена/создана: {db_dir}")
    
    def _table_exists(self, table_name: str) -> bool:
        """
        Проверяет существование таблицы в базе данных через запрос к sqlite_master.
        
        Args:
            table_name: Имя таблицы для проверки
        
        Returns:
            True если таблица существует, False в противном случае
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Ошибка при проверке существования таблицы: {e}")
            return False
    
    def _create_kbd_table(self, conn: sqlite3.Connection) -> None:
        """
        Создает таблицу kbd с указанной структурой.
        
        Args:
            conn: Соединение с базой данных
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS kbd (
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            term_0_25 REAL,
            term_0_5 REAL,
            term_0_75 REAL,
            term_1_0 REAL,
            term_2_0 REAL,
            term_3_0 REAL,
            term_5_0 REAL,
            term_7_0 REAL,
            term_10_0 REAL,
            term_15_0 REAL,
            term_20_0 REAL,
            term_30_0 REAL,
            PRIMARY KEY (date, time)
        )
        """
        
        try:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            self.logger.info("Таблица kbd успешно создана")
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при создании таблицы kbd: {e}", exc_info=True)
            raise
    
    def _load_csv_data(self) -> List[Dict[str, str]]:
        """
        Загружает данные из backend/data/zerocupon.csv.
        
        Returns:
            Список словарей с данными из CSV, где ключи - русские заголовки
        
        Raises:
            FileNotFoundError: Если файл не найден
        """
        # Определяем путь к файлу относительно текущего файла
        backend_dir = Path(__file__).parent.parent.parent
        data_dir = backend_dir / "app" / "data"
        csv_path = data_dir / "zerocupon.csv"
        
        if not csv_path.exists():
            error_msg = f"Файл zerocupon.csv не найден: {csv_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            records = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    # Пропускаем пустые строки
                    if not any(row.values()):
                        continue
                    records.append(row)
            
            return records
        except Exception as e:
            error_msg = f"Ошибка при загрузке данных из {csv_path}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise
    
    def _transform_kbd_data(self, raw_data: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Преобразует данные из CSV в формат таблицы.
        
        Применяет column_mapping для преобразования русских заголовков в английские.
        Преобразует числовые поля в REAL, используя NULL для пустых значений.
        
        Args:
            raw_data: Словарь с сырыми данными из CSV (ключи - русские заголовки, могут содержать BOM)
        
        Returns:
            Словарь с преобразованными данными для вставки в таблицу или None
        """
        # Нормализуем ключи, убирая BOM символ (\ufeff) если он есть
        normalized_data = {}
        for key, value in raw_data.items():
            # Убираем BOM символ из начала ключа
            normalized_key = key.lstrip('\ufeff')
            normalized_data[normalized_key] = value
        
        # Извлекаем обязательные поля для составного ключа
        date_value = normalized_data.get("Дата")
        time_value = normalized_data.get("Время")
        
        if not date_value or not time_value:
            self.logger.warning(
                f"Пропущена запись KBD: отсутствует date или time. "
                f"Данные: {raw_data}"
            )
            return None
        
        # Преобразуем данные с применением маппинга
        transformed = {
            "date": date_value.strip() if date_value else None,
            "time": time_value.strip() if time_value else None,
        }
        
        # Преобразуем числовые поля
        for russian_col, english_col in self.column_mapping.items():
            if russian_col in ["Дата", "Время"]:
                continue  # Уже обработаны выше
            
            value = normalized_data.get(russian_col, "").strip()
            if not value:
                transformed[english_col] = None
            else:
                try:
                    # Заменяем запятую на точку для корректного парсинга
                    value = value.replace(",", ".")
                    float_value = float(value)
                    # Проверяем на NaN и inf
                    if math.isnan(float_value) or math.isinf(float_value):
                        transformed[english_col] = None
                    else:
                        transformed[english_col] = float_value
                except (ValueError, TypeError):
                    transformed[english_col] = None
        
        return transformed
    
    def _insert_or_replace_kbd(self, conn: sqlite3.Connection, records: List[Dict[str, Any]]) -> None:
        """
        Вставляет или заменяет записи используя INSERT OR REPLACE INTO.
        
        Все операции выполняются в рамках одной транзакции с явным commit или rollback
        при ошибках.
        
        Args:
            conn: Соединение с базой данных
            records: Список словарей с данными для вставки/обновления
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        if not records:
            self.logger.warning("Нет данных для вставки")
            return
        
        insert_sql = """
        INSERT OR REPLACE INTO kbd (
            date, time, term_0_25, term_0_5, term_0_75, term_1_0,
            term_2_0, term_3_0, term_5_0, term_7_0, term_10_0,
            term_15_0, term_20_0, term_30_0
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            cursor = conn.cursor()
            inserted_count = 0
            
            for record in records:
                cursor.execute(insert_sql, (
                    record.get("date"),
                    record.get("time"),
                    record.get("term_0_25"),
                    record.get("term_0_5"),
                    record.get("term_0_75"),
                    record.get("term_1_0"),
                    record.get("term_2_0"),
                    record.get("term_3_0"),
                    record.get("term_5_0"),
                    record.get("term_7_0"),
                    record.get("term_10_0"),
                    record.get("term_15_0"),
                    record.get("term_20_0"),
                    record.get("term_30_0"),
                ))
                inserted_count += 1
            
            # Фиксируем транзакцию
            conn.commit()
            self.logger.info(f"Успешно вставлено/обновлено {inserted_count} записей в таблицу kbd")
        except sqlite3.Error as e:
            # Выполняем rollback при ошибке
            conn.rollback()
            self.logger.error(f"Ошибка при вставке данных в таблицу kbd: {e}", exc_info=True)
            raise
    
    def get_kbd_data(self) -> List[Dict[str, Any]]:
        """
        Извлекает сырые данные из таблицы kbd.
        
        Returns:
            Список словарей с данными из таблицы kbd, отсортированных по date DESC.
            Если таблица не существует, возвращает пустой список.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с БД
        """
        if not self._table_exists("kbd"):
            self.logger.warning("Таблица kbd не существует, get_kbd_data возвращает []")
            return []
        
        sql = "SELECT * FROM kbd ORDER BY date DESC"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                self.logger.debug(f"Выбрано {len(result)} записей из таблицы kbd")
                return result
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при get_kbd_data: {e}", exc_info=True)
            raise
