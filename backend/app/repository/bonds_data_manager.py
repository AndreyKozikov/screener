"""Менеджер данных для работы с таблицей облигаций в базе данных.

Этот модуль содержит класс BondsDataManager для управления данными облигаций:
создание таблицы, парсинг файлов, сохранение/обновление облигаций в БД.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from datetime import date

import orjson

from app.repository.constants import RATINGS_ORDER
from app.services.bond_filter import get_rating_index, standardize_rating
from app.services.emitent_service import get_emitent_service
from app.services.coupon_loader import get_coupon_loader


class BondsDataManager:
    """Менеджер данных для работы с таблицей облигаций в базе данных.
    
    Класс обеспечивает управление данными облигаций: создание таблицы,
    парсинг JSON файлов, преобразование и сохранение данных в БД.
    
    Основные методы:
        refresh(): Создание или обновление таблицы bonds из JSON файлов (миграции).
        _create_bonds_table(): Создание таблицы bonds с заданной структурой.
        _load_json_data(): Загрузка данных облигаций из JSON-файлов.
        _transform_bond_data(): Преобразование данных из JSON в формат таблицы БД.
        _insert_or_replace_bonds(): Вставка или замена записей в таблице bonds.
    """
    
    def __init__(self, db_path: Optional[Path] = None, data_dir: Optional[Path] = None):
        """Инициализирует экземпляр менеджера данных для работы с облигациями.
        
        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется путь по умолчанию: backend/db/bonds.db
            data_dir: Путь к директории с JSON-файлами данных. Если не указан,
                используется путь по умолчанию: backend/app/data
        
        Attributes:
            db_path: Путь к файлу базы данных.
            data_dir: Путь к директории с данными.
            logger: Логгер для записи событий и ошибок.
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
        """Создает или обновляет таблицу bonds в базе данных из JSON файлов.
        
        Выполняет полную синхронизацию данных облигаций между JSON-источниками
        и SQLite базой данных. Загружает данные из bonds.json, bonds_rating.json,
        bonds_emitent.json и coupons_data.json, преобразует их и сохраняет в БД.
        
        Returns:
            True если операция выполнена успешно, False в случае ошибки.
        
        Raises:
            Exception: При ошибках загрузки данных или работы с БД.
                Все ошибки логируются с полной информацией о стеке вызовов.
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
        """Создает директорию для базы данных, если она не существует.
        
        Проверяет наличие родительской директории для файла базы данных
        и создает её при необходимости. Используется перед созданием таблиц.
        """
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Директория для БД проверена/создана: {db_dir}")
    
    def _table_exists(self, table_name: str) -> bool:
        """Проверяет существование таблицы в базе данных.
        
        Args:
            table_name: Имя таблицы для проверки.
        
        Returns:
            True если таблица существует, False в противном случае.
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

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        """Проверяет существование колонки в таблице.
        
        Используется для обеспечения совместимости со старыми схемами БД,
        когда некоторые колонки могут отсутствовать.
        
        Args:
            table_name: Имя таблицы для проверки.
            column_name: Имя колонки для проверки.
        
        Returns:
            True если колонка существует, False в противном случае.
        """
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
        """Создает таблицу bonds с заданной структурой.
        
        Определяет схему таблицы bonds со всеми необходимыми колонками
        для хранения данных об облигациях. Выполняет CREATE TABLE IF NOT EXISTS.
        """
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
        """Загружает маппинги типов и видов облигаций из JSON-файлов.
        
        Загружает маппинги из bonds_type_mapping.json и bonds_type43_mapping.json
        для преобразования строковых значений типов и видов облигаций в числовые ID.
        
        Returns:
            Кортеж из двух словарей:
            - type_mapping: Маппинг типов облигаций (строка -> ID).
            - kind_mapping: Маппинг видов облигаций (строка -> ID).
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
        """Загружает данные облигаций из JSON-файлов и объединяет их.
        
        Загружает данные из bonds.json, объединяя секции securities, marketdata
        и marketdata_yields. Также загружает и добавляет данные из:
        - bonds_rating.json (рейтинги облигаций)
        - bonds_emitent.json (типы облигаций и рейтинги эмитентов)
        - coupons_data.json (данные о купонах)
        
        Returns:
            Список словарей с данными облигаций. Каждый словарь содержит
            объединенные данные из всех источников для одной облигации.
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
        """Загружает рейтинги облигаций из bonds_rating.json.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с ключом
            "all_ratings", содержащим список всех рейтингов облигации.
        """
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
        """Загружает данные эмитентов из bonds_emitent.json.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с данными
            эмитента, включая тип облигации и рейтинги эмитента.
        """
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
        """Загружает данные о купонах из coupons_data.json.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с данными
            о купонах облигации из секции "bonds" файла coupons_data.json.
        """
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
        """Вычисляет частоту купона (число выплат в год).
        
        Args:
            coupon_period: Период купона в днях. Если None или 0, возвращает None.
        
        Returns:
            Частота купона (округлённая до целого числа) или None,
            если период не указан или равен нулю.
        """
        if coupon_period is None or coupon_period == 0:
            return None
        
        try:
            frequency = 365 / coupon_period
            return round(frequency)
        except (ZeroDivisionError, TypeError):
            return None
    
    def _get_worst_rating(self, ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Определяет наихудший рейтинг из списка рейтингов.
        
        Фильтрует рейтинги со значением "Отозван", если есть другие рейтинги.
        Находит рейтинг с наибольшим индексом в шкале рейтингов.
        
        Args:
            ratings_list: Список словарей с рейтингами. Каждый словарь должен
                содержать ключ "rating_level_name_short_ru" с уровнем рейтинга.
        
        Returns:
            Словарь с наихудшим рейтингом или None, если список пуст или
            не содержит валидных рейтингов.
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
        """Получает итоговый рейтинг облигации и стандартизирует его.
        
        Сначала пытается получить рейтинг из данных облигации. Если рейтинга нет,
        пытается получить из данных эмитента. Выбирает наихудший рейтинг из всех
        доступных и стандартизирует его, удаляя русские индикаторы рынка.
        
        Args:
            bond_data: Словарь с данными облигации. Должен содержать ключ "RATINGS"
                со списком рейтингов облигации.
            emitent_data: Опциональный словарь с данными эмитента. Должен содержать
                ключ "cci_rating_companies" со списком рейтингов эмитента.
        
        Returns:
            Стандартизированная строка с рейтингом (например, "AAA", "AA+") или None,
            если рейтинги отсутствуют. Все русские индикаторы рынка ((RU), .ru, ru префикс)
            удаляются из рейтинга.
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
        """Преобразует данные из JSON в формат таблицы базы данных.
        
        Выполняет преобразование сырых данных облигации из JSON формата
        в формат, пригодный для вставки в таблицу bonds. Вычисляет производные
        поля (coupon_frequency, duration_years, coupon_yield_to_price) и применяет
        маппинги типов и видов облигаций.
        
        Args:
            raw_data: Словарь с сырыми данными облигации из JSON. Должен содержать
                обязательное поле "SECID".
            type_mapping: Словарь маппинга типов облигаций (строка -> ID).
            kind_mapping: Словарь маппинга видов облигаций (строка -> ID).
        
        Returns:
            Словарь с преобразованными данными для вставки в таблицу bonds или None,
            если SECID отсутствует в исходных данных.
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
        
        # Получаем текущую цену из marketdata_yields.PRICE, с fallback на PREVPRICE или PREVWAPRICE
        # PRICE из marketdata_yields - это цена, по которой была рассчитана доходность
        current_price = raw_data.get("PRICE") or raw_data.get("PREVPRICE") or raw_data.get("PREVWAPRICE")
        
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
        """Вставляет или заменяет записи в таблице bonds.
        
        Выполняет массовую вставку данных облигаций в таблицу bonds используя
        INSERT OR REPLACE INTO. Все операции выполняются в рамках одной транзакции.
        
        Args:
            bonds: Список словарей с данными облигаций для вставки/обновления.
                Каждый словарь должен содержать все поля таблицы bonds.
        
        Raises:
            Exception: При ошибках вставки данных. Все ошибки логируются
                с полной информацией о стеке вызовов.
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
