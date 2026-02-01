"""Загрузчик данных из JSON файлов с кэшированием.

Этот модуль содержит класс DataLoader для загрузки и кэширования данных об облигациях
из JSON файлов. Обеспечивает загрузку данных облигаций, рейтингов, типов облигаций
и метаданных (маппинги колонок, описания полей). Координирует обновление данных
через MoexClient и FileStorage.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import orjson

from app.models.bond import BondListItem
from app.repository.files.file_storage import FileStorage
from app.utils.rating_utils import get_rating_index
from app.services.coupon_loader import get_coupon_loader
from app.services.moex_client import MoexClient
from app.utils.logger import get_data_update_logger


class DataLoader:
    """Загрузчик данных из JSON файлов с кэшированием.

    Класс обеспечивает загрузку данных об облигациях из JSON файлов (bonds.json,
    bonds_rating.json, bonds_emitent.json) с кэшированием для повышения производительности.
    Координирует обновление данных: получение от MoexClient -> сохранение через FileStorage
    -> обновление локального кэша.

    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
        _moex_client: Клиент для загрузки данных с MOEX.
        _file_storage: Хранилище для чтения/записи JSON файлов.
        _bonds_cache: Кэш списка облигаций (BondListItem).
        _details_cache: Кэш детальной информации об облигациях.
        _columns_cache: Кэш маппингов колонок (поле -> отображаемое имя).
        _descriptions_cache: Кэш описаний полей.
    """

    def __init__(
        self,
        data_dir: Path,
        moex_client: Optional[MoexClient] = None,
        file_storage: Optional[FileStorage] = None,
    ):
        """Инициализирует загрузчик данных.

        Args:
            data_dir: Путь к директории с JSON файлами данных.
            moex_client: Клиент для загрузки данных с MOEX. Если None, создаётся экземпляр по умолчанию.
            file_storage: Хранилище для чтения/записи JSON. Если None, создаётся экземпляр по умолчанию.
        """
        self.data_dir = Path(data_dir)
        self._moex_client = moex_client if moex_client is not None else MoexClient()
        self._file_storage = file_storage if file_storage is not None else FileStorage()
        self._bonds_cache: Optional[List[BondListItem]] = None
        self._details_cache: Optional[Dict[str, Dict]] = None
        self._columns_cache: Optional[Dict[str, str]] = None
        self._descriptions_cache: Optional[Dict] = None
    
    async def get_bonds(self) -> List[BondListItem]:
        """Получает список всех облигаций (с кэшированием).
        
        Загружает список облигаций из файла bonds.json и преобразует их в объекты
        BondListItem. Данные кэшируются в памяти для повышения производительности.
        
        Returns:
            Список объектов BondListItem с данными облигаций. Облигации с режимом
            торгов SPOB исключаются из списка.
        """
        if self._bonds_cache is None:
            self._load_bonds_data()
        return self._bonds_cache
    
    async def get_bond_details(self) -> Dict[str, Dict]:
        """Получает детальную информацию об облигациях (с кэшированием).
        
        Загружает детальную информацию об облигациях из файла bonds.json, включая
        данные из секций securities, marketdata и marketdata_yields. Данные кэшируются
        в памяти для повышения производительности.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с детальной
            информацией, содержащий секции:
            - securities: Данные из секции securities
            - marketdata: Данные из секции marketdata
            - marketdata_yields: Список данных из секции marketdata_yields
        """
        if self._details_cache is None:
            self._load_bonds_data()
        return self._details_cache
    
    async def get_column_mapping(self) -> Dict[str, str]:
        """Получает маппинг колонок (с кэшированием).
        
        Загружает маппинг имен полей на отображаемые имена из файла columns.json.
        Данные кэшируются в памяти для повышения производительности.
        
        Returns:
            Словарь, где ключ - имя поля, значение - отображаемое имя колонки.
        """
        if self._columns_cache is None:
            self._columns_cache = self._load_column_mapping()
        return self._columns_cache
    
    async def get_descriptions(self) -> Dict:
        """Получает описания полей (с кэшированием).
        
        Загружает описания полей из файла describe.json. Данные кэшируются в памяти
        для повышения производительности.
        
        Returns:
            Словарь с описаниями полей из файла describe.json.
        """
        if self._descriptions_cache is None:
            self._descriptions_cache = self._load_descriptions()
        return self._descriptions_cache
    
    def refresh_bonds_dataset(self, source_url: str) -> Dict[str, int]:
        """Загружает последний набор данных об облигациях из внешнего источника.

        Координирует обновление: получает данные от MoexClient, сохраняет через
        FileStorage, обновляет локальный кэш.

        Args:
            source_url: URL для загрузки JSON данных об облигациях.
                Ожидается формат, совместимый с bonds.json (содержит секции
                securities, marketdata, marketdata_yields).

        Returns:
            Словарь с информацией о загруженном наборе данных, содержащий:
            - securities: Количество записей в секции securities
            - marketdata: Количество записей в секции marketdata
            - marketdata_yields: Количество записей в секции marketdata_yields

        Raises:
            RuntimeError: Если не удалось загрузить данные (сетевая ошибка, таймаут)
                или если получен некорректный JSON.
            OSError: Если не удалось записать данные в файл bonds.json.

        Note:
            После загрузки данных также выполняется запись в корневой файл bonds.json
            для совместимости с вспомогательными инструментами (например, Streamlit app).
            Ошибка записи корневого файла не прерывает процесс обновления.
        """
        logger = get_data_update_logger()
        logger.info("[REFRESH BONDS] Starting bonds dataset refresh from %s", source_url)

        payload = self._moex_client.fetch_bonds_json(source_url)

        bonds_path = self.data_dir / "bonds.json"
        logger.info("[REFRESH BONDS] Writing data to %s", bonds_path)
        self._file_storage.write_json(bonds_path, payload, indent=True, append_newline=True)

        root_bonds_path = self.data_dir.parents[2] / "bonds.json"
        try:
            logger.info("[REFRESH BONDS] Writing data to root bonds.json: %s", root_bonds_path)
            self._file_storage.write_json(root_bonds_path, payload, indent=True, append_newline=True)
        except OSError as exc:
            logger.warning("[REFRESH BONDS] Failed to write root bonds.json (non-critical): %s", exc)

        logger.info("[REFRESH BONDS] Clearing caches and reloading data")
        self._bonds_cache = None
        self._details_cache = None
        self._load_bonds_data()
        logger.info("[REFRESH BONDS] Data reloaded successfully")

        securities = len(payload.get("securities", {}).get("data", []))
        marketdata = len(payload.get("marketdata", {}).get("data", []))
        yields_count = len(payload.get("marketdata_yields", {}).get("data", []))
        summary = {
            "securities": securities,
            "marketdata": marketdata,
            "marketdata_yields": yields_count,
        }
        logger.info("[REFRESH BONDS] Refresh completed successfully. Summary: %s", summary)
        return summary
    
    def _load_bonds_data(self) -> None:
        """Загружает bonds.json и парсит данные в структуры.
        
        Загружает данные из файла bonds.json, парсит секции securities, marketdata
        и marketdata_yields, объединяет данные по SECID и создает объекты BondListItem
        для списка облигаций и словари для детальной информации. Также загружает и
        добавляет данные о рейтингах и типах облигаций из дополнительных файлов.
        
        Raises:
            IOError: Если не удалось прочитать файл bonds.json.
            orjson.JSONDecodeError: Если файл bonds.json содержит некорректный JSON.
        
        Note:
            Облигации с режимом торгов SPOB исключаются из списка. Данные о купонах
            загружаются из CouponLoader, если он инициализирован. Рейтинги загружаются
            из bonds_rating.json, типы облигаций - из bonds_emitent.json.
        """
        logger = get_data_update_logger()
        bonds_path = self.data_dir / "bonds.json"
        
        logger.info("[LOAD BONDS DATA] Starting to load bonds data from %s", bonds_path)
        try:
            data = self._file_storage.read_json(bonds_path)
            logger.info("[LOAD BONDS DATA] Successfully loaded JSON file from %s", bonds_path)
        except (OSError, orjson.JSONDecodeError) as exc:
            logger.error(
                "[LOAD BONDS DATA] Failed to load bonds.json from %s: %s: %s",
                bonds_path,
                type(exc).__name__,
                exc,
            )
            raise
        
        # Parse securities section
        securities = data.get("securities", {})
        sec_columns = securities.get("columns", [])
        sec_data = securities.get("data", [])
        logger.info(f"[LOAD BONDS DATA] Parsed {len(sec_data)} securities records")
        
        # Parse marketdata section
        marketdata = data.get("marketdata", {})
        md_columns = marketdata.get("columns", [])
        md_data = marketdata.get("data", [])
        logger.info(f"[LOAD BONDS DATA] Parsed {len(md_data)} marketdata records")
        
        # Parse marketdata_yields section
        yields = data.get("marketdata_yields", {})
        yields_columns = yields.get("columns", [])
        yields_data = yields.get("data", [])
        logger.info(f"[LOAD BONDS DATA] Parsed {len(yields_data)} yields records")
        
        # Build lookup dictionaries
        bonds_list = []
        details_map = {}
        skipped_spob_count = 0
        
        for row in sec_data:
            bond_dict = dict(zip(sec_columns, row))
            
            # Skip bonds with trading mode "SPOB" (режим торгов SPOB)
            boardid = bond_dict.get("BOARDID")
            if boardid and boardid.strip().upper() == "SPOB":
                skipped_spob_count += 1
                continue
            
            # Convert date strings to date objects
            for date_field in ["NEXTCOUPON", "MATDATE", "BUYBACKDATE", "PREVDATE", 
                             "OFFERDATE", "SETTLEDATE", "CALLOPTIONDATE", 
                             "PUTOPTIONDATE", "DATEYIELDFROMISSUER"]:
                if date_field in bond_dict and bond_dict[date_field]:
                    bond_dict[date_field] = self._parse_date(bond_dict[date_field])
            
            # Create list item (simplified) for table view
            try:
                # Save BONDTYPE43 from bonds.json (index 43) before it gets overwritten
                bondtype43_value = bond_dict.get("BONDTYPE")
                
                # Extract fields needed for BondListItem
                list_item_data = {
                    "SECID": bond_dict.get("SECID"),
                    "BOARDID": bond_dict.get("BOARDID"),
                    "SHORTNAME": bond_dict.get("SHORTNAME"),
                    "SECNAME": bond_dict.get("SECNAME"),
                    "ISIN": bond_dict.get("ISIN"),
                    "COUPONPERCENT": bond_dict.get("COUPONPERCENT"),
                    "MATDATE": bond_dict.get("MATDATE"),
                    "STATUS": bond_dict.get("STATUS"),
                    "FACEVALUE": bond_dict.get("FACEVALUE"),
                    "PREVPRICE": bond_dict.get("PREVPRICE"),
                    "YIELDATPREVWAPRICE": bond_dict.get("YIELDATPREVWAPRICE"),
                    "NEXTCOUPON": bond_dict.get("NEXTCOUPON"),
                    "BOARDNAME": bond_dict.get("BOARDNAME"),
                    "CALLOPTIONDATE": bond_dict.get("CALLOPTIONDATE"),
                    "PUTOPTIONDATE": bond_dict.get("PUTOPTIONDATE"),
                    "ACCRUEDINT": bond_dict.get("ACCRUEDINT"),
                    "COUPONPERIOD": bond_dict.get("COUPONPERIOD"),
                    "DURATION": None,  # Will be set from marketdata
                    "DURATIONWAPRICE": None,  # Will be set from marketdata_yields
                    "CURRENCYID": bond_dict.get("CURRENCYID"),
                    "LISTLEVEL": self._parse_int(bond_dict.get("LISTLEVEL")),
                    "BONDTYPE43": bondtype43_value,  # Вид облигации из bonds.json
                }
                
                list_item = BondListItem(**list_item_data)
                
                # COUPONVALUE теперь берётся из securities (bond_dict), удалён вызов coupon_loader
                
                bonds_list.append(list_item)
            except Exception as e:
                # Log validation errors but continue
                print(f"Error parsing bond {bond_dict.get('SECID')}: {e}")
                continue
            
            # Store detailed info (raw dict for flexibility)
            secid = bond_dict.get("SECID")
            if secid:
                # Save BONDTYPE from bonds.json (index 43) as BONDTYPE43 before it gets overwritten
                # by value from bonds_emitent.json
                if "BONDTYPE" in bond_dict:
                    bond_dict["BONDTYPE43"] = bond_dict.get("BONDTYPE")
                
                details_map[secid] = {
                    "securities": bond_dict,
                    "marketdata": {},
                    "marketdata_yields": []
                }
        
        # Add marketdata
        for row in md_data:
            md_dict = dict(zip(md_columns, row))
            secid = md_dict.get("SECID")
            boardid = md_dict.get("BOARDID")
            
            if secid and secid in details_map:
                details_map[secid]["marketdata"] = md_dict
                
                # Add TRADINGSTATUS and DURATION to list items (DURATION ONLY from marketdata)
                # Match by both SECID and BOARDID for accurate mapping
                if secid:
                    matched_bond = None
                    
                    # First, try to find exact match by SECID + BOARDID
                    if boardid:
                        for bond in bonds_list:
                            if bond.SECID == secid and bond.BOARDID == boardid:
                                matched_bond = bond
                                break
                    
                    # If no exact match found, find first bond with matching SECID
                    if matched_bond is None:
                        for bond in bonds_list:
                            if bond.SECID == secid:
                                matched_bond = bond
                                break
                    
                    if matched_bond:
                        if md_dict.get("TRADINGSTATUS"):
                            matched_bond.TRADINGSTATUS = md_dict.get("TRADINGSTATUS")
                        
                        # Load DURATION exclusively from marketdata section
                        duration_raw = md_dict.get("DURATION")
                        
                        # Always try to set DURATION from marketdata if it exists
                        # Check if DURATION key exists in the dictionary (even if value is None/0)
                        if "DURATION" in md_dict:
                            try:
                                if duration_raw is None:
                                    # Explicitly set to None if key exists but value is None
                                    matched_bond.DURATION = None
                                elif isinstance(duration_raw, (int, float)):
                                    # Convert to float (including 0, which is valid)
                                    matched_bond.DURATION = float(duration_raw)
                                elif isinstance(duration_raw, str):
                                    duration_str = duration_raw.strip()
                                    if duration_str and duration_str.lower() not in ('', 'nan', 'none', 'null', 'n/a'):
                                        try:
                                            parsed = float(duration_str)
                                            matched_bond.DURATION = parsed
                                        except (ValueError, TypeError):
                                            matched_bond.DURATION = None
                                    else:
                                        matched_bond.DURATION = None
                                else:
                                    matched_bond.DURATION = None
                            except (ValueError, TypeError, AttributeError) as e:
                                # If parsing fails, set to None
                                matched_bond.DURATION = None
                        # If DURATION key doesn't exist in marketdata, leave bond.DURATION as is (None or previously set)
        
        # Add yields data and extract DURATIONWAPRICE for list items (DURATION is loaded only from marketdata)
        for row in yields_data:
            yields_dict = dict(zip(yields_columns, row))
            secid = yields_dict.get("SECID")
            if secid and secid in details_map:
                details_map[secid]["marketdata_yields"].append(yields_dict)
                
                # Add DURATIONWAPRICE to list item if available (use first yield record)
                # NOTE: DURATION is loaded exclusively from marketdata, not from marketdata_yields
                durationwaprice = yields_dict.get("DURATIONWAPRICE")
                if durationwaprice is not None:
                    for bond in bonds_list:
                        if bond.SECID == secid:
                            if bond.DURATIONWAPRICE is None:
                                bond.DURATIONWAPRICE = durationwaprice
                            break
        
        # Load and add ratings data
        logger.info("[LOAD BONDS DATA] Loading ratings data")
        ratings_map = self._load_ratings_map()
        self._add_ratings_to_bonds(bonds_list, ratings_map)
        
        # Also add ratings to details_map for BondDetail
        for secid, rating_info in ratings_map.items():
            if secid in details_map:
                all_ratings = rating_info.get("all_ratings", [])
                # Store all ratings
                details_map[secid]["securities"]["RATINGS"] = all_ratings
                
                # Get worst rating
                worst_rating = self._get_worst_rating(all_ratings)
                if worst_rating:
                    details_map[secid]["securities"]["RATING_AGENCY"] = worst_rating.get("agency_name_short_ru", "").strip()
                    details_map[secid]["securities"]["RATING_LEVEL"] = worst_rating.get("rating_level_name_short_ru", "").strip()
        
        # Load and add bond types from bonds_emitent.json
        logger.info("[LOAD BONDS DATA] Loading bond types data")
        bondtype_map = self._load_bondtype_map()
        self._add_bondtypes_to_bonds(bonds_list, bondtype_map)
        
        # Also add bondtype to details_map for BondDetail
        for secid, bondtype in bondtype_map.items():
            if secid in details_map:
                # Add bondtype to securities section in details_map
                details_map[secid]["securities"]["BONDTYPE"] = bondtype
        
        self._bonds_cache = bonds_list
        self._details_cache = details_map
        
        logger.info(f"[LOAD BONDS DATA] Successfully loaded {len(bonds_list)} bonds, {len(details_map)} bond details, {len(ratings_map)} ratings, {len(bondtype_map)} bond types")
        if skipped_spob_count > 0:
            logger.info(f"[LOAD BONDS DATA] Skipped {skipped_spob_count} bonds with trading mode SPOB")
    
    def _load_column_mapping(self) -> Dict[str, str]:
        """Загружает columns.json и строит маппинг полей на отображаемые имена.
        
        Загружает данные из файла columns.json и создает словарь для преобразования
        имен полей в отображаемые имена колонок. Обрабатывает секции securities,
        marketdata и marketdata_yields.
        
        Returns:
            Словарь, где ключ - имя поля, значение - отображаемое имя колонки.
            Если файл не существует или некорректен, возвращает пустой словарь.
        """
        columns_path = self.data_dir / "columns.json"
        data = self._file_storage.read_json(columns_path)
        
        mapping = {}
        
        for section_name in ["securities", "marketdata", "marketdata_yields"]:
            section = data.get(section_name, {})
            columns = section.get("columns", [])
            rows = section.get("data", [])
            
            try:
                name_idx = columns.index("name")
                short_title_idx = columns.index("short_title")
            except ValueError:
                continue
            
            for row in rows:
                if len(row) > max(name_idx, short_title_idx):
                    field_name = row[name_idx]
                    display_name = row[short_title_idx]
                    if field_name and display_name:
                        mapping[str(field_name)] = str(display_name)
        
        return mapping
    
    def _load_descriptions(self) -> Dict:
        """Загружает describe.json с описаниями полей.
        
        Returns:
            Словарь с описаниями полей из файла describe.json.
            Если файл не существует или некорректен, может вызвать исключение.
        """
        desc_path = self.data_dir / "describe.json"
        return self._file_storage.read_json(desc_path)
    
    def clear_bonds_cache(self) -> None:
        """Очищает кэш облигаций для принудительной перезагрузки.
        
        Сбрасывает кэши списка облигаций и детальной информации. Используется
        после обновления данных о купонах для принудительной перезагрузки данных
        с актуальными значениями купонов.
        """
        self._bonds_cache = None
        self._details_cache = None
    
    def clear_metadata_cache(self) -> None:
        """Очищает кэш метаданных (колонки и описания) для принудительной перезагрузки.
        
        Сбрасывает кэши маппингов колонок и описаний полей. Используется после
        обновления метаданных для принудительной перезагрузки данных.
        """
        logger = get_data_update_logger()
        logger.info("[CLEAR METADATA CACHE] Clearing metadata cache (columns and descriptions)")
        self._columns_cache = None
        self._descriptions_cache = None
        logger.info("[CLEAR METADATA CACHE] Metadata cache cleared successfully")
    
    @staticmethod
    def _parse_int(value: any) -> Optional[int]:
        """Парсит целочисленное значение из различных форматов.
        
        Преобразует значение в целое число, поддерживая различные типы входных данных
        (int, str, float). Обрабатывает некорректные значения.
        
        Args:
            value: Значение для преобразования в целое число. Может быть int, str, float
                или другим типом.
        
        Returns:
            Целое число или None, если значение не может быть преобразовано в int.
        """
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _load_ratings_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает рейтинги из bonds_rating.json и возвращает как словарь.
        
        Загружает данные о рейтингах облигаций из файла bonds_rating.json и создает
        словарь для быстрого доступа. Поддерживает различные форматы данных (новый
        формат с ключом "ratings", старый формат с ключом "cci_rating_securities",
        прямой массив рейтингов).
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с данными:
            - ratings: Список валидных рейтингов (с agency_name_short_ru)
            - all_ratings: Список всех рейтингов (для выбора наихудшего)
            Если файл не существует или некорректен, возвращает пустой словарь.
        """
        ratings_path = self.data_dir / "bonds_rating.json"
        ratings_map = {}
        
        if not ratings_path.exists():
            print(f"[DATA LOADER] Ratings file not found: {ratings_path}, skipping ratings")
            return ratings_map
        
        try:
            ratings_data = self._file_storage.read_json(ratings_path)
            
            print(f"[DATA LOADER] Loaded ratings for {len(ratings_data)} bonds")
            
            # Create a lookup map for quick access
            for secid, rating_entry in ratings_data.items():
                ratings_list = []
                
                if isinstance(rating_entry, dict):
                    # New format: {last_updated: "...", ratings: [...]}
                    if "ratings" in rating_entry:
                        ratings_list = rating_entry["ratings"]
                    # Old format: {cci_rating_securities: [...]}
                    elif "cci_rating_securities" in rating_entry:
                        ratings_list = rating_entry["cci_rating_securities"]
                # Old format: direct array
                elif isinstance(rating_entry, list):
                    ratings_list = rating_entry
                
                # Store all ratings
                if isinstance(ratings_list, list) and len(ratings_list) > 0:
                    # Filter valid ratings (must have agency_name_short_ru)
                    valid_ratings = [
                        r for r in ratings_list 
                        if isinstance(r, dict) and r.get("agency_name_short_ru", "").strip()
                    ]
                    
                    if valid_ratings:
                        ratings_map[secid] = {
                            "ratings": valid_ratings,
                            "all_ratings": valid_ratings  # Keep all for worst rating selection
                        }
            
        except (orjson.JSONDecodeError, IOError) as exc:
            print(f"[DATA LOADER] ERROR: Failed to load ratings file - {type(exc).__name__}: {str(exc)}")
            # Continue without ratings if file is corrupted or can't be read
        
        return ratings_map
    
    def _get_worst_rating(self, ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Получает наихудший рейтинг из списка рейтингов.
        
        Определяет наихудший рейтинг из списка, исключая рейтинги со значением "Отозван",
        если есть другие рейтинги. Использует шкалу рейтингов для определения позиции
        рейтинга.
        
        Args:
            ratings_list: Список словарей с рейтингами. Каждый словарь должен содержать
                ключ "rating_level_name_short_ru" с уровнем рейтинга.
        
        Returns:
            Словарь с наихудшим рейтингом (с наибольшим индексом в шкале) или None,
            если список пуст или не содержит валидных рейтингов.
        """
        if not ratings_list:
            return None
        
        # Filter out "Отозван" ratings if other ratings exist
        non_revoked_ratings = [
            r for r in ratings_list
            if isinstance(r, dict) and r.get("rating_level_name_short_ru", "").lower() not in ["отозван", "отозвано"]
        ]
        
        # If we have non-revoked ratings, use them; otherwise use all ratings
        ratings_to_check = non_revoked_ratings if non_revoked_ratings else ratings_list
        
        if not ratings_to_check:
            return None
        
        # Find worst rating (highest index in rating scale)
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
    
    def _add_ratings_to_bonds(self, bonds_list: List[BondListItem], ratings_map: Dict[str, Dict[str, Any]]) -> None:
        """Добавляет рейтинги из ratings_map к облигациям, выбирая наихудший рейтинг.
        
        Для каждой облигации из списка добавляет все рейтинги и определяет наихудший
        рейтинг, который сохраняется в полях RATING_AGENCY и RATING_LEVEL.
        
        Args:
            bonds_list: Список объектов BondListItem для добавления рейтингов.
            ratings_map: Словарь с рейтингами, где ключ - SECID облигации, значение -
                словарь с ключами "all_ratings" (список всех рейтингов).
        """
        ratings_added = 0
        for bond in bonds_list:
            if bond.SECID in ratings_map:
                rating_info = ratings_map[bond.SECID]
                all_ratings = rating_info.get("all_ratings", [])
                
                # Store all ratings
                bond.RATINGS = all_ratings
                
                # Get worst rating
                worst_rating = self._get_worst_rating(all_ratings)
                if worst_rating:
                    bond.RATING_AGENCY = worst_rating.get("agency_name_short_ru", "").strip()
                    bond.RATING_LEVEL = worst_rating.get("rating_level_name_short_ru", "").strip()
                    ratings_added += 1
        
        print(f"[DATA LOADER] Added ratings to {ratings_added} bonds")
    
    def _load_bondtype_map(self) -> Dict[str, Optional[str]]:
        """Загружает типы облигаций из bonds_emitent.json и возвращает как словарь.
        
        Загружает данные о типах облигаций из файла bonds_emitent.json и создает
        словарь для быстрого доступа. Извлекает поле "type" из каждой записи эмитента.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - тип облигации (строка)
            или None, если тип отсутствует. Если файл не существует или некорректен,
            возвращает пустой словарь.
        """
        emitent_path = self.data_dir / "bonds_emitent.json"
        bondtype_map = {}
        
        if not emitent_path.exists():
            print(f"[DATA LOADER] Emitent file not found: {emitent_path}, skipping bond types")
            return bondtype_map
        
        try:
            emitent_data = self._file_storage.read_json(emitent_path)
            
            print(f"[DATA LOADER] Loaded emitent data for {len(emitent_data)} bonds")
            
            # Create a lookup map for quick access
            for secid, emitent_entry in emitent_data.items():
                if isinstance(emitent_entry, dict):
                    bondtype = emitent_entry.get("type")
                    if bondtype and isinstance(bondtype, str):
                        bondtype_map[secid] = bondtype.strip()
            
            print(f"[DATA LOADER] Extracted bond types for {len(bondtype_map)} bonds")
            
        except (orjson.JSONDecodeError, IOError) as exc:
            print(f"[DATA LOADER] ERROR: Failed to load emitent file - {type(exc).__name__}: {str(exc)}")
            # Continue without bond types if file is corrupted or can't be read
        
        return bondtype_map
    
    def _add_bondtypes_to_bonds(self, bonds_list: List[BondListItem], bondtype_map: Dict[str, Optional[str]]) -> None:
        """Добавляет типы облигаций из bondtype_map к облигациям.
        
        Для каждой облигации из списка устанавливает поле BONDTYPE из словаря типов.
        
        Args:
            bonds_list: Список объектов BondListItem для добавления типов.
            bondtype_map: Словарь с типами облигаций, где ключ - SECID облигации,
                значение - тип облигации (строка) или None.
        """
        bondtypes_added = 0
        for bond in bonds_list:
            if bond.SECID in bondtype_map:
                bond.BONDTYPE = bondtype_map[bond.SECID]
                bondtypes_added += 1
        
        print(f"[DATA LOADER] Added bond types to {bondtypes_added} bonds")
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Парсит строку даты в объект date.
        
        Преобразует строку с датой в формате YYYY-MM-DD в объект date.
        Обрабатывает некорректные значения и специальное значение "0000-00-00".
        
        Args:
            date_str: Строка с датой в формате YYYY-MM-DD.
        
        Returns:
            Объект date или None, если строка некорректна, пуста или равна "0000-00-00".
        """
        if not date_str or date_str == "0000-00-00":
            return None
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


# Singleton instance
_data_loader: Optional[DataLoader] = None


def init_data_loader(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр загрузчика данных.

    Создаёт глобальный экземпляр DataLoader с указанной директорией данных
    и внедрёнными MoexClient и FileStorage. Должен быть вызван перед
    использованием get_data_loader().

    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _data_loader
    _data_loader = DataLoader(
        data_dir,
        moex_client=MoexClient(),
        file_storage=FileStorage(),
    )


def get_data_loader() -> DataLoader:
    """Получает singleton экземпляр загрузчика данных.
    
    Returns:
        Экземпляр DataLoader для работы с данными из JSON файлов.
    
    Raises:
        RuntimeError: Если загрузчик не был инициализирован через init_data_loader().
    """
    if _data_loader is None:
        raise RuntimeError("Data loader not initialized")
    return _data_loader
