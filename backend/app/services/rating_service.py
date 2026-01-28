"""Сервис для работы с данными рейтингов облигаций из API MOEX.

Этот модуль содержит класс RatingService для загрузки, кэширования и управления
данными о рейтингах облигаций из API Московской биржи. Данные сохраняются в JSON
файл и обновляются при необходимости.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import orjson
import requests

from app.services.emitent_service import get_emitent_service


class RatingService:
    """Сервис для работы с данными рейтингов облигаций из API MOEX.
    
    Класс обеспечивает загрузку данных о рейтингах облигаций из API Московской биржи,
    кэширование данных в JSON файл и управление обновлением данных. Поддерживает
    получение рейтингов по SECID и BOARDID, автоматическое определение emitent_id
    и специальную обработку ОФЗ (автоматическое присвоение рейтинга AAA).
    
    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
        rating_file: Путь к файлу для хранения данных о рейтингах.
        _rating_cache: Кэш загруженных данных о рейтингах.
    """
    
    def __init__(self, data_dir: Path):
        """Инициализирует сервис для работы с рейтингами.
        
        Args:
            data_dir: Путь к директории с JSON файлами данных.
        """
        self.data_dir = data_dir
        self.rating_file = data_dir / "bonds_rating.json"
        self._rating_cache: Optional[Dict[str, Dict]] = None
    
    def _load_rating_data(self) -> Dict[str, Dict]:
        """Загружает данные о рейтингах из JSON файла.
        
        Загружает данные из файла bonds_rating.json с кэшированием. При первом
        вызове загружает данные из файла и сохраняет в кэш. При последующих вызовах
        возвращает данные из кэша.
        
        Returns:
            Словарь с данными о рейтингах. Ключ - SECID облигации, значение -
            словарь с данными рейтингов (новый формат: {"last_updated": "...", "ratings": [...]}
            или старый формат: {"cci_rating_securities": [...]} или прямой массив).
            Если файл не существует или поврежден, возвращает пустой словарь и создает новый файл.
        """
        if self._rating_cache is not None:
            print(f"[RATING SERVICE] Using cached rating data (in-memory cache)")
            return self._rating_cache
        
        print(f"[RATING SERVICE] Loading rating data from file: {self.rating_file}")
        
        if not self.rating_file.exists():
            print(f"[RATING SERVICE] File does not exist, creating empty file")
            # Create empty file if it doesn't exist
            self._rating_cache = {}
            self._save_rating_data()
            print(f"[RATING SERVICE] Empty file created")
            return self._rating_cache
        
        try:
            file_size = self.rating_file.stat().st_size
            print(f"[RATING SERVICE] File exists, size: {file_size} bytes")
            
            with open(self.rating_file, 'rb') as f:
                self._rating_cache = orjson.loads(f.read())
            
            cached_count = len(self._rating_cache)
            print(f"[RATING SERVICE] Successfully loaded {cached_count} rating entries from file")
        except (orjson.JSONDecodeError, IOError) as exc:
            print(f"[RATING SERVICE] ERROR: Failed to load file - {type(exc).__name__}: {str(exc)}")
            print(f"[RATING SERVICE] Creating fresh empty file")
            # If file is corrupted or can't be read, start fresh
            self._rating_cache = {}
            self._save_rating_data()
        
        return self._rating_cache
    
    def _filter_rating_keys(self, rating_item: Dict[str, Any]) -> Dict[str, Any]:
        """Фильтрует запись рейтинга, оставляя только необходимые ключи.
        
        Извлекает из словаря рейтинга только поля, необходимые для работы приложения.
        Упрощает структуру данных для использования в других компонентах.
        
        Args:
            rating_item: Словарь с данными рейтинга со всеми полями из API MOEX.
        
        Returns:
            Отфильтрованный словарь с только необходимыми ключами:
            - agency_id: Идентификатор агентства рейтинга
            - agency_name_short_ru: Краткое название агентства на русском
            - rating_level_id: Идентификатор уровня рейтинга
            - rating_date: Дата присвоения рейтинга
            - rating_level_name_short_ru: Краткое название уровня рейтинга на русском
        """
        required_keys = [
            "agency_id",
            "agency_name_short_ru",
            "rating_level_id",
            "rating_date",
            "rating_level_name_short_ru"
        ]
        
        return {key: rating_item.get(key) for key in required_keys if key in rating_item}
    
    def _create_empty_rating(self) -> List[Dict[str, Any]]:
        """Создает пустую запись рейтинга со значениями по умолчанию.
        
        Используется когда рейтинг не найден или произошла ошибка при загрузке.
        Возвращает список с одной записью рейтинга с пустыми значениями.
        
        Returns:
            Список с одним словарем рейтинга со значениями по умолчанию
            (все поля пустые или равны 0).
        """
        return [
            {
                "agency_id": 0,
                "agency_name_short_ru": "",
                "rating_level_id": 0,
                "rating_date": "",
                "rating_level_name_short_ru": ""
            }
        ]
    
    def _create_ofz_aaa_rating(self) -> List[Dict[str, Any]]:
        """Создает рейтинг AAA для ОФЗ (государственных облигаций) с emitent_id = 1228.
        
        ОФЗ облигации автоматически получают рейтинг AAA без запроса к API MOEX,
        так как они являются государственными облигациями с наивысшим уровнем надежности.
        
        Returns:
            Список с одним словарем рейтинга AAA с полем agency_name_short_ru = "Автоматический".
        """
        return [
            {
                "agency_id": 0,
                "agency_name_short_ru": "Автоматический",
                "rating_level_id": 0,
                "rating_date": "",
                "rating_level_name_short_ru": "AAA"
            }
        ]
    
    def _is_data_stale(self, last_updated: str) -> bool:
        """Проверяет, устарели ли данные (старше одного месяца).
        
        Определяет, превышает ли возраст данных 30 дней. Используется для принятия
        решения об обновлении данных из API MOEX.
        
        Args:
            last_updated: Строка с датой последнего обновления в формате ISO (YYYY-MM-DD).
        
        Returns:
            True если данные старше 30 дней, False в противном случае.
            Если дата некорректна или не может быть распознана, возвращает True
            (данные считаются устаревшими).
        """
        try:
            last_date = date.fromisoformat(last_updated)
            today = date.today()
            days_diff = (today - last_date).days
            is_stale = days_diff > 30  # More than 30 days (one month)
            
            print(f"[RATING SERVICE] Data age check: last_updated={last_updated}, days_diff={days_diff}, is_stale={is_stale}")
            return is_stale
        except (ValueError, TypeError) as exc:
            print(f"[RATING SERVICE] ERROR: Could not parse last_updated date '{last_updated}': {exc}")
            # If date is invalid, consider data stale to force update
            return True
    
    def _save_rating_data(self) -> None:
        """Сохраняет данные о рейтингах в JSON файл.
        
        Записывает кэшированные данные в файл bonds_rating.json с форматированием
        (отступы и перенос строки). Создает директорию для файла при необходимости.
        """
        if self._rating_cache is None:
            self._rating_cache = {}
        
        entries_count = len(self._rating_cache)
        print(f"[RATING SERVICE] Saving {entries_count} rating entries to file: {self.rating_file}")
        
        serialized = orjson.dumps(
            self._rating_cache,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        file_size = len(serialized)
        self.rating_file.write_bytes(serialized)
        print(f"[RATING SERVICE] File saved successfully, size: {file_size} bytes")
    
    def _get_emitent_id_from_cache(self, secid: str) -> Optional[str]:
        """Получает emitent_id из кэшированных данных эмитента (bonds_emitent.json).
        
        Ищет emitent_id для облигации в кэше данных эмитентов. Используется для
        определения emitent_id перед запросом рейтингов к API MOEX.
        
        Args:
            secid: Идентификатор облигации (SECID) для поиска emitent_id.
        
        Returns:
            Emitent ID (строка) или None, если данные не найдены в кэше.
        """
        try:
            emitent_service = get_emitent_service()
            emitent_data = emitent_service.get_emitent_by_secid(secid)
            
            if emitent_data is None:
                print(f"[RATING SERVICE] Emitent data not found in cache for SECID: {secid}")
                return None
            
            emitent_id = emitent_data.get("emitent_id")
            if emitent_id is not None:
                emitent_id_str = str(emitent_id)
                print(f"[RATING SERVICE] Found emitent ID in cache: {emitent_id_str} for SECID: {secid}")
                return emitent_id_str
            
            print(f"[RATING SERVICE] Emitent ID not found in cached data for SECID: {secid}")
            return None
            
        except Exception as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: Failed to get emitent ID from cache - {error_type}: {str(exc)}")
            return None
    
    def _extract_emitent_id_from_api(self, secid: str) -> Optional[str]:
        """Извлекает emitent_id из API MOEX путем загрузки данных об облигации.
        
        Выполняет HTTP запрос к API MOEX для получения данных об облигации по SECID
        и извлекает emitent_id из секции description ответа.
        
        Args:
            secid: Идентификатор облигации (SECID) для запроса к API MOEX.
        
        Returns:
            Emitent ID (строка) или None, если emitent_id не найден в ответе API.
        
        Raises:
            RuntimeError: Если не удалось загрузить данные (сетевая ошибка, таймаут)
                или если формат ответа API неожиданный.
        """
        print(f"[RATING SERVICE] Fetching emitent ID from MOEX API for SECID: {secid}")
        
        api_url = f"https://iss.moex.com/iss/securities/{secid}.json?iss.json=extended&iss.meta=off"
        print(f"[RATING SERVICE] API URL: {api_url}")
        
        try:
            print(f"[RATING SERVICE] Sending HTTP GET request to API...")
            response = requests.get(
                api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30
            )
            
            print(f"[RATING SERVICE] API response: status_code={response.status_code}")
            response.raise_for_status()
            
            # Parse JSON response
            try:
                json_data = response.json()
                print(f"[RATING SERVICE] JSON parsed successfully, type: {type(json_data).__name__}")
                
                # Expected format: [{"charsetinfo": {...}}, {"description": [...], "boards": [...]}]
                if not isinstance(json_data, list) or len(json_data) < 2:
                    print(f"[RATING SERVICE] ERROR: Unexpected JSON structure - expected list with at least 2 elements")
                    return None
                
                # Find the element with "description" key
                description_data = None
                for item in json_data:
                    if isinstance(item, dict) and "description" in item:
                        description_data = item["description"]
                        break
                
                if not description_data:
                    print(f"[RATING SERVICE] ERROR: Could not find 'description' in JSON response")
                    return None
                
                if not isinstance(description_data, list):
                    print(f"[RATING SERVICE] ERROR: 'description' is not a list")
                    return None
                
                # Find EMITTER_ID in description array
                print(f"[RATING SERVICE] Searching for EMITTER_ID in description array ({len(description_data)} items)...")
                for desc_item in description_data:
                    if isinstance(desc_item, dict) and desc_item.get("name") == "EMITTER_ID":
                        emitent_id = desc_item.get("value")
                        if emitent_id is not None:
                            # Convert to string if it's a number
                            emitent_id_str = str(emitent_id)
                            print(f"[RATING SERVICE] Found emitent ID: {emitent_id_str}")
                            return emitent_id_str
                
                print(f"[RATING SERVICE] ERROR: Could not find EMITTER_ID in description array")
                return None
                
            except json.JSONDecodeError as exc:
                print(f"[RATING SERVICE] ERROR: Failed to parse JSON response - {str(exc)}")
                raise RuntimeError(f"Invalid JSON response from API: {exc}") from exc
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: API request failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to fetch emitent ID from API for {secid}: {exc}") from exc
        
        print(f"[RATING SERVICE] ERROR: Could not extract emitent ID from API response")
        return None
    
    def _fetch_rating_via_api(self, secid: str, emitent_id: str) -> Optional[List[Dict[str, Any]]]:
        """Загружает данные рейтинга из API MOEX используя emitent_id.
        
        Выполняет HTTP запрос к API MOEX для получения рейтингов облигации по SECID
        и emitent_id. Парсит ответ в различных форматах и извлекает список рейтингов
        из секции cci_rating_securities.
        
        Args:
            secid: Идентификатор облигации (SECID) для запроса рейтингов.
            emitent_id: Идентификатор эмитента (emitent_id) для формирования URL запроса.
        
        Returns:
            Список словарей с данными рейтингов (отфильтрованных по необходимым ключам)
            или None, если рейтинги не найдены. Если все рейтинги отфильтрованы,
            возвращает пустой рейтинг.
        
        Raises:
            RuntimeError: Если не удалось загрузить данные (сетевая ошибка, таймаут)
                или если формат ответа API неожиданный.
        
        Note:
            API MOEX может возвращать данные в различных форматах (список, словарь,
            вложенные структуры). Метод обрабатывает все возможные форматы и извлекает
            данные из секции cci_rating_securities.
        """
        # Construct API URL
        api_url = (
            f"https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}/"
            f"securities/isin_{secid}.json?iss.json=extended&iss.meta=off"
        )
        
        print(f"[RATING SERVICE] Fetching rating via MOEX API")
        print(f"[RATING SERVICE] API URL: {api_url}")
        
        try:
            print(f"[RATING SERVICE] Sending HTTP GET request to API...")
            response = requests.get(
                api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30
            )
            
            print(f"[RATING SERVICE] API response: status_code={response.status_code}")
            response.raise_for_status()
            
            # Parse JSON response
            try:
                json_data = response.json()
                print(f"[RATING SERVICE] JSON parsed successfully, type: {type(json_data).__name__}")
                
                # Handle different response formats and extract ratings list
                ratings_list = []
                
                # Format 1: List that may contain charsetinfo and cci_rating_securities
                if isinstance(json_data, list):
                    print(f"[RATING SERVICE] Response is a list with {len(json_data)} elements")
                    # Search for element containing cci_rating_securities
                    for item in json_data:
                        if isinstance(item, dict):
                            # Check if this item has cci_rating_securities
                            if "cci_rating_securities" in item:
                                ratings_data = item["cci_rating_securities"]
                                if isinstance(ratings_data, list):
                                    ratings_list = ratings_data
                                    print(f"[RATING SERVICE] Found cci_rating_securities in list element: {len(ratings_list)} entries")
                                    break
                            # Skip charsetinfo objects
                            elif "charsetinfo" in item:
                                print(f"[RATING SERVICE] Skipping charsetinfo element")
                                continue
                    
                    # If not found in nested structure, treat as direct list of ratings
                    if not ratings_list:
                        # Check if all items are rating objects (have agency_id or similar)
                        potential_ratings = [item for item in json_data if isinstance(item, dict) and "agency_id" in item]
                        if potential_ratings:
                            ratings_list = potential_ratings
                            print(f"[RATING SERVICE] Found {len(ratings_list)} rating entries (direct list format)")
                
                # Format 2: Dict with cci_rating_securities key
                elif isinstance(json_data, dict):
                    # Check for direct cci_rating_securities array
                    if "cci_rating_securities" in json_data:
                        ratings_data = json_data["cci_rating_securities"]
                        
                        # If it's a dict with columns/data structure (MOEX format)
                        if isinstance(ratings_data, dict) and "data" in ratings_data:
                            columns = ratings_data.get("columns", [])
                            data_rows = ratings_data.get("data", [])
                            
                            print(f"[RATING SERVICE] Found MOEX format: {len(columns)} columns, {len(data_rows)} rows")
                            
                            # Convert to list of dicts
                            for row in data_rows:
                                if len(row) == len(columns):
                                    rating_dict = dict(zip(columns, row))
                                    ratings_list.append(rating_dict)
                            
                            print(f"[RATING SERVICE] Converted to {len(ratings_list)} rating entries")
                        
                        # If it's already a list
                        elif isinstance(ratings_data, list):
                            ratings_list = ratings_data
                            print(f"[RATING SERVICE] Found {len(ratings_list)} rating entries")
                
                # Format 3: Nested structure - search recursively
                if not ratings_list and isinstance(json_data, dict):
                    print(f"[RATING SERVICE] Searching recursively in JSON structure...")
                    for key, value in json_data.items():
                        if isinstance(value, dict) and "cci_rating_securities" in value:
                            ratings_data = value["cci_rating_securities"]
                            if isinstance(ratings_data, dict) and "data" in ratings_data:
                                columns = ratings_data.get("columns", [])
                                data_rows = ratings_data.get("data", [])
                                
                                for row in data_rows:
                                    if len(row) == len(columns):
                                        rating_dict = dict(zip(columns, row))
                                        ratings_list.append(rating_dict)
                                
                                print(f"[RATING SERVICE] Found in nested structure: {len(ratings_list)} rating entries")
                                break
                            elif isinstance(ratings_data, list):
                                ratings_list = ratings_data
                                print(f"[RATING SERVICE] Found in nested structure: {len(ratings_list)} rating entries")
                                break
                
                # Filter ratings to keep only required keys
                if ratings_list:
                    print(f"[RATING SERVICE] Processing {len(ratings_list)} rating entries from API")
                    
                    # Filter each rating and collect valid ones
                    filtered_ratings = []
                    for idx, rating in enumerate(ratings_list):
                        if not isinstance(rating, dict):
                            print(f"[RATING SERVICE] WARNING: Rating entry {idx} is not a dict, skipping")
                            continue
                        
                        filtered = self._filter_rating_keys(rating)
                        # Only add non-empty dictionaries
                        if filtered and len(filtered) > 0:
                            filtered_ratings.append(filtered)
                            agency_name = filtered.get("agency_name_short_ru", "unknown")
                            print(f"[RATING SERVICE] Rating {idx + 1}/{len(ratings_list)}: {agency_name} - filtered successfully")
                        else:
                            print(f"[RATING SERVICE] WARNING: Rating entry {idx} filtered to empty, skipping")
                    
                    print(f"[RATING SERVICE] Successfully filtered {len(filtered_ratings)} rating entries (from {len(ratings_list)} total)")
                    
                    if not filtered_ratings:
                        print(f"[RATING SERVICE] WARNING: All ratings were filtered out, returning empty rating")
                        return self._create_empty_rating()
                    
                    # Return just the list, not wrapped in cci_rating_securities
                    return filtered_ratings
            
            except json.JSONDecodeError as exc:
                print(f"[RATING SERVICE] ERROR: Failed to parse JSON response - {str(exc)}")
                raise RuntimeError(f"Invalid JSON response from API: {exc}") from exc
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: API request failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to fetch rating from API for {secid}: {exc}") from exc
        
        print(f"[RATING SERVICE] ERROR: Could not extract cci_rating_securities from API response")
        return None
    
    def _fetch_rating_from_moex(self, secid: str, boardid: str) -> Optional[List[Dict[str, Any]]]:
        """Загружает данные рейтинга из MOEX по SECID и BOARDID.
        
        Выполняет многошаговую стратегию для получения рейтинга облигации:
        1. Сначала пытается получить emitent_id из кэша данных эмитентов
        2. Если не найден в кэше, загружает из API MOEX
        3. Если emitent_id = 1228 (ОФЗ), автоматически присваивает рейтинг AAA
        4. Иначе загружает данные рейтинга через API MOEX используя emitent_id
        
        Args:
            secid: Идентификатор облигации (SECID) для поиска рейтинга.
            boardid: Идентификатор торговой площадки (BOARDID). Не используется
                в новой реализации, оставлен для совместимости.
        
        Returns:
            Список словарей с данными рейтингов или None, если рейтинг не найден.
            Если emitent_id не найден или произошла ошибка, возвращает пустой рейтинг.
        
        Note:
            ОФЗ облигации (emitent_id = 1228) автоматически получают рейтинг AAA
            без запроса к API MOEX, так как они являются государственными облигациями.
        """
        print(f"[RATING SERVICE] Fetching rating data from MOEX")
        print(f"[RATING SERVICE] SECID: {secid}, BOARDID: {boardid}")
        
        # Step 1: Try to get emitent ID from cache first
        print(f"[RATING SERVICE] Step 1: Checking emitent ID in cache...")
        emitent_id = self._get_emitent_id_from_cache(secid)
        
        # Step 2: If not in cache, fetch from MOEX API
        if not emitent_id:
            print(f"[RATING SERVICE] Step 2: Emitent ID not in cache, fetching from MOEX API...")
            try:
                emitent_id = self._extract_emitent_id_from_api(secid)
            except Exception as exc:
                error_type = type(exc).__name__
                print(f"[RATING SERVICE] ERROR: Failed to extract emitent ID from API - {error_type}: {str(exc)}")
                print(f"[RATING SERVICE] No rating data available for this bond, returning empty rating")
                return self._create_empty_rating()
        
        if not emitent_id:
            print(f"[RATING SERVICE] WARNING: Could not find emitent ID for {secid}")
            print(f"[RATING SERVICE] No rating data available for this bond, returning empty rating")
            # Return empty rating instead of raising error
            return self._create_empty_rating()
        
        # Step 2.5: Check if this is OFZ (emitent_id = 1228) - assign AAA rating automatically
        emitent_id_int = None
        try:
            emitent_id_int = int(emitent_id)
        except (ValueError, TypeError):
            pass
        
        if emitent_id_int == 1228:
            print(f"[RATING SERVICE] OFZ bond detected (emitent_id=1228), automatically assigning AAA rating")
            return self._create_ofz_aaa_rating()
        
        # Step 3: Fetch rating via API using emitent ID
        print(f"[RATING SERVICE] Step 3: Fetching rating via API using emitent ID: {emitent_id}...")
        rating_data = self._fetch_rating_via_api(secid, emitent_id)
        
        if rating_data is None:
            print(f"[RATING SERVICE] WARNING: Could not extract rating data from API response for {secid}")
            print(f"[RATING SERVICE] Returning empty rating")
            return self._create_empty_rating()
        
        print(f"[RATING SERVICE] Successfully fetched rating data via API")
        return rating_data
    
    def get_rating(self, secid: str, boardid: str, force_refresh: bool = False, force_update_all: bool = False) -> List[Dict[str, Any]]:
        """Получает данные рейтинга для конкретной облигации по SECID и BOARDID.
        
        Сначала проверяет локальный файл. Если force_refresh=True, загружает из API MOEX
        когда данные отсутствуют или устарели. Если force_refresh=False, возвращает
        только кэшированные данные (без сетевых запросов).
        
        Args:
            secid: Идентификатор облигации (SECID) для получения рейтинга.
            boardid: Идентификатор торговой площадки (BOARDID). Не используется
                в новой реализации, оставлен для совместимости.
            force_refresh: Если True, загружает из API MOEX когда данные отсутствуют
                или устарели (старше одного месяца). Если False, возвращает только
                кэшированные данные без сетевых запросов.
            force_update_all: Если True, игнорирует дату last_updated и всегда загружает
                из API MOEX когда force_refresh=True. Если False, учитывает проверку даты.
        
        Returns:
            Список словарей с данными рейтингов, каждый словарь содержит ключи:
            - agency_id: Идентификатор агентства рейтинга
            - agency_name_short_ru: Краткое название агентства на русском
            - rating_level_id: Идентификатор уровня рейтинга
            - rating_date: Дата присвоения рейтинга
            - rating_level_name_short_ru: Краткое название уровня рейтинга на русском
            Если рейтинг не найден, возвращается список с одной пустой записью рейтинга.
        
        Note:
            Данные считаются устаревшими если они старше 30 дней. Поддерживаются
            различные форматы кэшированных данных (новый формат с last_updated,
            старый формат с cci_rating_securities, прямой массив).
        """
        print(f"[RATING SERVICE] Getting rating for SECID={secid}, BOARDID={boardid}, force_refresh={force_refresh}, force_update_all={force_update_all}")
        
        rating_data = self._load_rating_data()
        
        # Check if data exists in local file
        if secid in rating_data:
            cached_entry = rating_data[secid]
            # Handle different formats
            if isinstance(cached_entry, dict):
                # New format with last_updated and ratings
                if "ratings" in cached_entry:
                    ratings_list = cached_entry["ratings"]
                    last_updated = cached_entry.get("last_updated", "")
                    ratings_count = len(ratings_list) if isinstance(ratings_list, list) else 0
                    print(f"[RATING SERVICE] Found cached data for {secid} with {ratings_count} rating entries (last updated: {last_updated})")
                    
                    # Check if data needs to be refreshed (older than one month)
                    # If force_update_all is True, skip date check and always fetch
                    if force_update_all:
                        if force_refresh:
                            print(f"[RATING SERVICE] force_update_all=True, ignoring date check, fetching fresh data from MOEX...")
                            # Continue to fetch fresh data below
                        else:
                            print(f"[RATING SERVICE] force_update_all=True but force_refresh=False, returning cached data")
                            if not isinstance(ratings_list, list):
                                print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                                ratings_list = []
                            return ratings_list
                    elif last_updated and not self._is_data_stale(last_updated):
                        print(f"[RATING SERVICE] Cached data is fresh, returning cached data (no MOEX fetch needed)")
                        # Ensure we return a list
                        if not isinstance(ratings_list, list):
                            print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                            ratings_list = []
                        return ratings_list
                    else:
                        if force_refresh:
                            print(f"[RATING SERVICE] Cached data is stale (older than one month), fetching fresh data from MOEX...")
                            # Continue to fetch fresh data below
                        else:
                            print(f"[RATING SERVICE] Cached data is stale, but force_refresh=False, returning cached data anyway")
                            # Ensure we return a list
                            if not isinstance(ratings_list, list):
                                print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                                ratings_list = []
                            return ratings_list
                # Old format with cci_rating_securities (no date, consider stale)
                elif "cci_rating_securities" in cached_entry:
                    ratings_list = cached_entry.get("cci_rating_securities", [])
                    ratings_count = len(ratings_list) if isinstance(ratings_list, list) else 0
                    print(f"[RATING SERVICE] Found cached data for {secid} with {ratings_count} rating entries (old format, no date)")
                    if force_refresh:
                        print(f"[RATING SERVICE] force_refresh=True, fetching fresh data from MOEX...")
                        # Continue to fetch fresh data below
                    else:
                        print(f"[RATING SERVICE] force_refresh=False, returning cached data (old format)")
                        # Ensure we return a list
                        if not isinstance(ratings_list, list):
                            print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                            ratings_list = []
                        return ratings_list
            # Old format: direct array (no date, consider stale)
            elif isinstance(cached_entry, list):
                ratings_count = len(cached_entry)
                print(f"[RATING SERVICE] Found cached data for {secid} with {ratings_count} rating entries (old format - direct array, no date)")
                if force_refresh:
                    print(f"[RATING SERVICE] force_refresh=True, fetching fresh data from MOEX...")
                    # Continue to fetch fresh data below
                else:
                    print(f"[RATING SERVICE] force_refresh=False, returning cached data (old format)")
                    # Ensure we return a list
                    if not isinstance(cached_entry, list):
                        print(f"[RATING SERVICE] WARNING: cached_entry is not a list, converting...")
                        cached_entry = []
                    return cached_entry
        
        # No cached data found or force_refresh is True
        if not force_refresh:
            print(f"[RATING SERVICE] No cached data found for {secid}, but force_refresh=False, returning empty rating")
            return self._create_empty_rating()
        
        print(f"[RATING SERVICE] No cached data found for {secid}, fetching from MOEX...")
        
        # Fetch from MOEX website
        try:
            fresh_data = self._fetch_rating_from_moex(secid, boardid)
            print(f"[RATING SERVICE] Successfully processed data from MOEX")
        except Exception as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: Failed to fetch from MOEX - {error_type}: {str(exc)}")
            # On error, save empty rating instead of raising exception
            print(f"[RATING SERVICE] Saving empty rating due to error")
            fresh_data = self._create_empty_rating()
        
        # Ensure we have data (should always be the case now)
        if fresh_data is None:
            print(f"[RATING SERVICE] WARNING: No data received, using empty rating")
            fresh_data = self._create_empty_rating()
        
        # Save to file (save with last_updated date)
        print(f"[RATING SERVICE] Saving data to cache...")
        if self._rating_cache is None:
            self._rating_cache = {}
        
        # Save with last_updated date
        today = date.today().isoformat()
        self._rating_cache[secid] = {
            "last_updated": today,
            "ratings": fresh_data
        }
        print(f"[RATING SERVICE] Saving with last_updated date: {today}")
        self._save_rating_data()
        
        print(f"[RATING SERVICE] Data saved successfully, returning to caller")
        # Ensure we return a list
        if not isinstance(fresh_data, list):
            print(f"[RATING SERVICE] WARNING: fresh_data is not a list, converting...")
            fresh_data = []
        return fresh_data


# Singleton instance
_rating_service: Optional[RatingService] = None


def init_rating_service(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр сервиса рейтингов.
    
    Создает глобальный экземпляр RatingService с указанной директорией данных.
    Должен быть вызван перед использованием get_rating_service().
    
    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _rating_service
    _rating_service = RatingService(data_dir)


def get_rating_service() -> RatingService:
    """Получает singleton экземпляр сервиса рейтингов.
    
    Returns:
        Экземпляр RatingService для работы с данными рейтингов облигаций.
    
    Raises:
        RuntimeError: Если сервис не был инициализирован через init_rating_service().
    """
    if _rating_service is None:
        raise RuntimeError("Rating service not initialized")
    return _rating_service

