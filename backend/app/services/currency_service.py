"""Сервис для работы с курсами валют от ЦБ РФ.

Этот модуль содержит класс CurrencyService для загрузки, кэширования и управления
курсами валют из API Центрального банка Российской Федерации. Данные сохраняются
в JSON файл и обновляются при необходимости.
"""

import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

import orjson
import requests

from app.utils.logger import get_data_update_logger


class CurrencyService:
    """Сервис для работы с курсами валют от ЦБ РФ.
    
    Класс обеспечивает загрузку курсов валют из API Центрального банка РФ,
    кэширование данных в JSON файл и управление обновлением данных. Поддерживает
    получение курсов для конкретной даты с автоматическим поиском ближайших
    доступных курсов при отсутствии данных.
    
    Attributes:
        INTERESTED_CURRENCIES: Список кодов валют, которые интересуют приложение
            (EUR, USD, CNY).
        CBR_BASE_URL: Базовый URL API ЦБ РФ для получения курсов валют.
        data_dir: Путь к директории с данными.
        currency_file: Путь к файлу для хранения курсов валют.
        _currency_cache: Кэш загруженных данных о курсах валют.
        logger: Логгер для записи событий и ошибок.
    """
    
    INTERESTED_CURRENCIES: List[str] = ['EUR', 'USD', 'CNY']
    """Список кодов валют, которые интересуют приложение."""
    
    CBR_BASE_URL: str = "https://www.cbr.ru/scripts/XML_daily.asp"
    """Базовый URL API ЦБ РФ для получения курсов валют."""
    
    def __init__(self, data_dir: Path):
        """Инициализирует сервис для работы с курсами валют.
        
        Args:
            data_dir: Путь к директории с JSON файлами данных.
        """
        self.data_dir = data_dir
        self.currency_file = data_dir / "currency_rates.json"
        self._currency_cache: Optional[List[Dict[str, Any]]] = None
        self.logger = get_data_update_logger()
    
    def _load_currency_data(self) -> List[Dict[str, Any]]:
        """Загружает данные о курсах валют из JSON файла.
        
        Загружает данные из файла currency_rates.json с кэшированием. При первом
        вызове загружает данные из файла и сохраняет в кэш. При последующих вызовах
        возвращает данные из кэша.
        
        Returns:
            Список словарей с данными о курсах валют. Каждый словарь содержит:
            - date: Дата в формате YYYY-MM-DD
            - source_date: Дата из ответа API ЦБ РФ
            - rates: Словарь с курсами валют (ключ - код валюты, значение - данные курса)
            Если файл не существует или поврежден, возвращает пустой список.
        """
        if self._currency_cache is not None:
            self.logger.info("[CURRENCY SERVICE] Using cached currency data (in-memory cache)")
            return self._currency_cache
        
        self.logger.info(f"[CURRENCY SERVICE] Loading currency data from file: {self.currency_file}")
        
        if not self.currency_file.exists():
            self.logger.info("[CURRENCY SERVICE] File does not exist, creating empty file")
            self._currency_cache = []
            self._save_currency_data()
            return self._currency_cache
        
        try:
            file_size = self.currency_file.stat().st_size
            self.logger.info(f"[CURRENCY SERVICE] File exists, size: {file_size} bytes")
            
            with open(self.currency_file, 'rb') as f:
                self._currency_cache = orjson.loads(f.read())
            
            if not isinstance(self._currency_cache, list):
                self.logger.warning("[CURRENCY SERVICE] Data is not a list, initializing empty list")
                self._currency_cache = []
                self._save_currency_data()
                return self._currency_cache
            
            cached_count = len(self._currency_cache)
            self.logger.info(f"[CURRENCY SERVICE] Successfully loaded {cached_count} currency rate entries from file")
        except (orjson.JSONDecodeError, IOError) as exc:
            self.logger.error(f"[CURRENCY SERVICE] ERROR: Failed to load file - {type(exc).__name__}: {str(exc)}")
            self.logger.info("[CURRENCY SERVICE] Creating fresh empty file")
            self._currency_cache = []
            self._save_currency_data()
        
        return self._currency_cache
    
    def _save_currency_data(self) -> None:
        """Сохраняет данные о курсах валют в JSON файл.
        
        Записывает кэшированные данные в файл currency_rates.json с форматированием
        (отступы и перенос строки). Создает директорию для файла при необходимости.
        """
        if self._currency_cache is None:
            self._currency_cache = []
        
        entries_count = len(self._currency_cache)
        self.logger.info(f"[CURRENCY SERVICE] Saving {entries_count} currency rate entries to file: {self.currency_file}")
        
        serialized = orjson.dumps(
            self._currency_cache,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        file_size = len(serialized)
        self.currency_file.write_bytes(serialized)
        self.logger.info(f"[CURRENCY SERVICE] File saved successfully, size: {file_size} bytes")
    
    def _has_rates_for_date(self, target_date: date) -> bool:
        """Проверяет, существуют ли курсы валют для указанной даты.
        
        Args:
            target_date: Дата для проверки наличия курсов.
        
        Returns:
            True если в кэше есть запись с курсами для указанной даты,
            False в противном случае.
        """
        currency_data = self._load_currency_data()
        
        target_date_str = target_date.isoformat()
        
        for entry in currency_data:
            if isinstance(entry, dict) and entry.get("date") == target_date_str:
                return True
        
        return False
    
    def _fetch_rates_from_cbr(self, target_date: date) -> Dict[str, Any]:
        """Загружает курсы валют из API ЦБ РФ для указанной даты.
        
        Выполняет HTTP запрос к API Центрального банка РФ для получения курсов валют
        на указанную дату. Парсит XML ответ и извлекает курсы для интересующих валют
        (EUR, USD, CNY). Рассчитывает курс за 1 единицу валюты с учетом номинала.
        
        Args:
            target_date: Дата для получения курсов валют.
        
        Returns:
            Словарь с данными о курсах валют, содержащий:
            - date: Дата в формате YYYY-MM-DD
            - source_date: Дата из ответа API ЦБ РФ (атрибут Date элемента ValCurs)
            - rates: Словарь с курсами валют. Ключ - код валюты (EUR, USD, CNY),
              значение - словарь с данными курса:
              - code: Код валюты
              - rate: Курс за 1 единицу валюты в рублях
              - nominal: Номинал валюты
              - original_value: Исходное значение курса из API
        
        Raises:
            RuntimeError: Если не удалось загрузить данные (сетевая ошибка, таймаут)
                или если не удалось распарсить XML ответ.
        
        Note:
            API ЦБ РФ возвращает XML в кодировке windows-1251. Метод автоматически
            определяет кодировку и декодирует ответ. Курсы рассчитываются за 1 единицу
            валюты с учетом номинала (например, если номинал 10, то курс делится на 10).
        """
        # Format date as DD/MM/YYYY for CBR API
        date_str = target_date.strftime("%d/%m/%Y")
        url = f"{self.CBR_BASE_URL}?date_req={date_str}"
        
        self.logger.info(f"[CURRENCY SERVICE] Fetching currency rates from CBR API for date: {date_str}")
        self.logger.info(f"[CURRENCY SERVICE] URL: {url}")
        
        try:
            # Use requests for better error handling
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30
            )
            
            self.logger.info(f"[CURRENCY SERVICE] API response: status_code={response.status_code}")
            response.raise_for_status()
            
            # Parse XML response
            # CBR API returns XML in windows-1251 encoding
            content = response.content
            try:
                # Try to decode as windows-1251
                xml_text = content.decode('windows-1251')
            except UnicodeDecodeError:
                # Fallback to utf-8
                xml_text = content.decode('utf-8')
            
            root = ET.fromstring(xml_text)
            
            # Extract date from ValCurs element
            val_curs_date = root.get('Date', '')
            self.logger.info(f"[CURRENCY SERVICE] XML parsed, ValCurs date: {val_curs_date}")
            
            # Parse all currencies
            rates = {}
            for valute in root.findall('Valute'):
                char_code = valute.find('CharCode')
                value = valute.find('Value')
                nominal = valute.find('Nominal')
                
                if char_code is not None and value is not None:
                    code = char_code.text
                    # Value is stored as string with comma as decimal separator
                    value_str = value.text.replace(',', '.') if value.text else '0'
                    nominal_val = int(nominal.text) if nominal is not None and nominal.text else 1
                    
                    try:
                        # Calculate rate per 1 unit (handle nominal)
                        rate_value = float(value_str) / nominal_val
                        
                        if code in self.INTERESTED_CURRENCIES:
                            rates[code] = {
                                'code': code,
                                'rate': rate_value,
                                'nominal': nominal_val,
                                'original_value': value.text
                            }
                            self.logger.info(f"[CURRENCY SERVICE] Found {code}: {rate_value} RUB (nominal: {nominal_val})")
                    except (ValueError, TypeError) as exc:
                        self.logger.warning(f"[CURRENCY SERVICE] WARNING: Could not parse rate for {code}: {exc}")
            
            # Check if we found all interested currencies
            missing = set(self.INTERESTED_CURRENCIES) - set(rates.keys())
            if missing:
                self.logger.warning(f"[CURRENCY SERVICE] WARNING: Missing currencies: {missing}")
            
            result = {
                'date': target_date.isoformat(),
                'source_date': val_curs_date,
                'rates': rates
            }
            
            self.logger.info(f"[CURRENCY SERVICE] Successfully fetched rates for {len(rates)} currencies")
            return result
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[CURRENCY SERVICE] ERROR: API request failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to fetch currency rates from CBR API: {exc}") from exc
        except ET.ParseError as exc:
            self.logger.error(f"[CURRENCY SERVICE] ERROR: Failed to parse XML - {str(exc)}")
            raise RuntimeError(f"Failed to parse XML response from CBR API: {exc}") from exc
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[CURRENCY SERVICE] ERROR: Unexpected error - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to fetch currency rates: {exc}") from exc
    
    def _find_previous_rates(self, target_date: date, currency_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Находит ближайшую предыдущую запись с непустыми курсами.
        
        Ищет в списке записей о курсах валют запись с датой <= target_date, которая
        содержит непустые курсы. Возвращает самую свежую из таких записей.
        
        Args:
            target_date: Дата, от которой выполняется поиск назад.
            currency_data: Список записей о курсах валют для поиска.
        
        Returns:
            Словарь с данными о курсах валют (содержит date, source_date, rates)
            или None, если не найдено ни одной записи с непустыми курсами.
        """
        target_date_str = target_date.isoformat()
        
        # Filter entries with date <= target_date and non-empty rates
        valid_entries = []
        for entry in currency_data:
            if not isinstance(entry, dict):
                continue
            
            entry_date_str = entry.get("date")
            if not entry_date_str:
                continue
            
            try:
                entry_date = date.fromisoformat(entry_date_str)
                if entry_date <= target_date:
                    rates = entry.get("rates", {})
                    # Check if rates dict is not empty
                    if rates and isinstance(rates, dict) and len(rates) > 0:
                        valid_entries.append((entry_date, entry))
            except (ValueError, TypeError):
                continue
        
        if not valid_entries:
            return None
        
        # Sort by date descending (most recent first)
        valid_entries.sort(key=lambda x: x[0], reverse=True)
        
        # Return the most recent entry with rates
        _, most_recent_entry = valid_entries[0]
        self.logger.info(f"[CURRENCY SERVICE] Found previous rates entry for date: {most_recent_entry.get('date')}")
        return most_recent_entry
    
    def get_rates(self, target_date: Optional[date] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Получает курсы валют для указанной даты.
        
        Загружает курсы валют из кэша (JSON файл) или из API ЦБ РФ, если данные
        отсутствуют, устарели или запрошено принудительное обновление. Если курсы
        для указанной даты отсутствуют или пусты, возвращает ближайшую предыдущую
        запись с непустыми курсами.
        
        Args:
            target_date: Дата для получения курсов. Если не указана, используется
                сегодняшняя дата.
            force_refresh: Если True, принудительно загружает курсы из API ЦБ РФ,
                игнорируя кэш. По умолчанию False.
        
        Returns:
            Словарь с данными о курсах валют, содержащий:
            - date: Дата в формате YYYY-MM-DD
            - source_date: Дата из ответа API ЦБ РФ (может быть пустой строкой)
            - rates: Словарь с курсами валют для интересующих валют (EUR, USD, CNY)
            Если курсы не найдены, возвращается структура с пустым словарем rates.
        
        Note:
            При отсутствии курсов для указанной даты выполняется поиск ближайшей
            предыдущей записи с непустыми курсами. Это позволяет использовать актуальные
            курсы даже если для конкретной даты данные отсутствуют.
        """
        if target_date is None:
            target_date = date.today()
        
        target_date_str = target_date.isoformat()
        self.logger.info(f"[CURRENCY SERVICE] Getting currency rates for date: {target_date_str}, force_refresh={force_refresh}")
        
        currency_data = self._load_currency_data()
        
        # Check if rates exist for this date
        if not force_refresh and self._has_rates_for_date(target_date):
            # Find and return existing rates
            for entry in currency_data:
                if isinstance(entry, dict) and entry.get("date") == target_date_str:
                    rates = entry.get("rates", {})
                    # Check if rates are not empty
                    if rates and isinstance(rates, dict) and len(rates) > 0:
                        self.logger.info(f"[CURRENCY SERVICE] Found cached rates for {target_date_str}")
                        return entry
                    else:
                        # Entry exists but has empty rates, look for previous entry
                        self.logger.info(f"[CURRENCY SERVICE] Found entry for {target_date_str} but rates are empty, looking for previous entry")
                        previous_entry = self._find_previous_rates(target_date, currency_data)
                        if previous_entry:
                            return previous_entry
        
        # Rates not found or force_refresh is True
        if not force_refresh:
            self.logger.info(f"[CURRENCY SERVICE] No cached rates for {target_date_str}, but force_refresh=False")
            # Try to find previous entry with rates
            previous_entry = self._find_previous_rates(target_date, currency_data)
            if previous_entry:
                self.logger.info(f"[CURRENCY SERVICE] Using previous rates entry for date: {previous_entry.get('date')}")
                return previous_entry
            # Return empty structure if no previous entry found
            return {
                'date': target_date_str,
                'source_date': '',
                'rates': {}
            }
        
        self.logger.info(f"[CURRENCY SERVICE] Fetching fresh rates from CBR API for {target_date_str}...")
        
        # Fetch from CBR API
        try:
            fresh_data = self._fetch_rates_from_cbr(target_date)
            self.logger.info(f"[CURRENCY SERVICE] Successfully fetched rates from CBR API")
            
            # Check if fetched rates are not empty
            rates = fresh_data.get("rates", {})
            if not rates or not isinstance(rates, dict) or len(rates) == 0:
                self.logger.warning(f"[CURRENCY SERVICE] Fetched rates are empty for {target_date_str}, looking for previous entry")
                previous_entry = self._find_previous_rates(target_date, currency_data)
                if previous_entry:
                    return previous_entry
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[CURRENCY SERVICE] ERROR: Failed to fetch rates - {error_type}: {str(exc)}")
            # Try to find previous entry with rates
            previous_entry = self._find_previous_rates(target_date, currency_data)
            if previous_entry:
                self.logger.info(f"[CURRENCY SERVICE] Using previous rates entry after fetch error for date: {previous_entry.get('date')}")
                return previous_entry
            # Return empty structure on error if no previous entry found
            return {
                'date': target_date_str,
                'source_date': '',
                'rates': {}
            }
        
        # Save to file (append if not exists for this date, or update if exists)
        if self._currency_cache is None:
            self._currency_cache = []
        
        # Check if entry for this date already exists
        existing_index = None
        for idx, entry in enumerate(self._currency_cache):
            if isinstance(entry, dict) and entry.get("date") == target_date_str:
                existing_index = idx
                break
        
        if existing_index is not None:
            # Update existing entry
            self.logger.info(f"[CURRENCY SERVICE] Updating existing entry for {target_date_str}")
            self._currency_cache[existing_index] = fresh_data
        else:
            # Append new entry
            self.logger.info(f"[CURRENCY SERVICE] Appending new entry for {target_date_str}")
            self._currency_cache.append(fresh_data)
        
        # Save to file
        self._save_currency_data()
        
        self.logger.info(f"[CURRENCY SERVICE] Rates saved successfully")
        return fresh_data
    
    def refresh_rates(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Принудительно обновляет курсы валют для указанной даты из API ЦБ РФ.
        
        Выполняет принудительную загрузку курсов валют из API ЦБ РФ для указанной даты
        и сохраняет их в файл. Используется для ручного обновления данных.
        
        Args:
            target_date: Дата для обновления курсов. Если не указана, используется
                сегодняшняя дата.
        
        Returns:
            Словарь с результатом обновления, содержащий:
            - status: Статус операции ("ok" или "error")
            - date: Дата в формате YYYY-MM-DD
            - rates_count: Количество загруженных курсов валют (при успехе)
            - error: Сообщение об ошибке (при ошибке)
            - updated: Флаг успешного обновления (True или False)
        """
        if target_date is None:
            target_date = date.today()
        
        target_date_str = target_date.isoformat()
        self.logger.info(f"[CURRENCY SERVICE] Refreshing currency rates for date: {target_date_str}")
        
        try:
            rates_data = self.get_rates(target_date, force_refresh=True)
            
            return {
                'status': 'ok',
                'date': target_date_str,
                'rates_count': len(rates_data.get('rates', {})),
                'updated': True
            }
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[CURRENCY SERVICE] ERROR: Failed to refresh rates - {error_type}: {str(exc)}")
            return {
                'status': 'error',
                'date': target_date_str,
                'error': str(exc),
                'updated': False
            }


# Singleton instance
_currency_service: Optional[CurrencyService] = None


def init_currency_service(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр сервиса курсов валют.
    
    Создает глобальный экземпляр CurrencyService с указанной директорией данных.
    Должен быть вызван перед использованием get_currency_service().
    
    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _currency_service
    _currency_service = CurrencyService(data_dir)


def get_currency_service() -> CurrencyService:
    """Получает singleton экземпляр сервиса курсов валют.
    
    Returns:
        Экземпляр CurrencyService для работы с курсами валют.
    
    Raises:
        RuntimeError: Если сервис не был инициализирован через init_currency_service().
    """
    if _currency_service is None:
        raise RuntimeError("Currency service not initialized")
    return _currency_service

