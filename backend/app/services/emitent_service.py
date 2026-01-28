"""Сервис для работы с данными эмитентов из API MOEX.

Этот модуль содержит класс EmitentService для загрузки, кэширования и управления
данными об эмитентах облигаций из API Московской биржи. Данные сохраняются в JSON
файл и обновляются при необходимости.
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson
import requests

from app.services.data_loader import get_data_loader


class EmitentService:
    """Сервис для работы с данными эмитентов из API MOEX.
    
    Класс обеспечивает загрузку данных об эмитентах облигаций из API Московской биржи,
    кэширование данных в JSON файл и управление обновлением данных. Поддерживает
    получение данных по SECID или ISIN, загрузку рейтингов эмитентов и массовое
    обновление данных для всех облигаций.
    
    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
        emitent_file: Путь к файлу для хранения данных об эмитентах.
        _emitent_cache: Кэш загруженных данных об эмитентах.
    """
    
    def __init__(self, data_dir: Path):
        """Инициализирует сервис для работы с эмитентами.
        
        Args:
            data_dir: Путь к директории с JSON файлами данных.
        """
        self.data_dir = data_dir
        self.emitent_file = data_dir / "bonds_emitent.json"
        self._emitent_cache: Optional[Dict[str, Dict]] = None
    
    def _load_emitent_data(self) -> Dict[str, Dict]:
        """Загружает данные об эмитентах из JSON файла.
        
        Загружает данные из файла bonds_emitent.json с кэшированием. При первом
        вызове загружает данные из файла и сохраняет в кэш. При последующих вызовах
        возвращает данные из кэша.
        
        Returns:
            Словарь с данными об эмитентах. Ключ - SECID облигации, значение -
            словарь с данными эмитента из API MOEX. Если файл не существует или
            поврежден, возвращает пустой словарь и создает новый файл.
        """
        if self._emitent_cache is not None:
            return self._emitent_cache
        
        if not self.emitent_file.exists():
            # Create empty file if it doesn't exist
            self._emitent_cache = {}
            self._save_emitent_data()
            return self._emitent_cache
        
        try:
            with open(self.emitent_file, 'rb') as f:
                self._emitent_cache = orjson.loads(f.read())
        except (orjson.JSONDecodeError, IOError):
            # If file is corrupted or can't be read, start fresh
            self._emitent_cache = {}
            self._save_emitent_data()
        
        return self._emitent_cache
    
    def get_secid_to_emitent_title_index(self) -> Dict[str, str]:
        """Получает индекс маппинга SECID на название эмитента.
        
        Создает словарь для быстрого поиска названия эмитента по SECID облигации.
        Используется для фильтрации облигаций по эмитенту в сервисном слое.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - название эмитента
            (emitent_title). Если у облигации нет названия эмитента или оно пустое,
            облигация не включается в индекс.
        """
        emitent_data = self._load_emitent_data()
        index = {}
        for secid, emitent_info in emitent_data.items():
            emitent_title = emitent_info.get("emitent_title")
            if emitent_title and emitent_title.strip():
                index[secid] = emitent_title.strip()
        return index
    
    def _save_emitent_data(self) -> None:
        """Сохраняет данные об эмитентах в JSON файл.
        
        Записывает кэшированные данные в файл bonds_emitent.json с форматированием
        (отступы и перенос строки). Создает директорию для файла при необходимости.
        """
        if self._emitent_cache is None:
            self._emitent_cache = {}
        
        serialized = orjson.dumps(
            self._emitent_cache,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        self.emitent_file.write_bytes(serialized)
    
    def get_emitent_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Получает данные эмитента по SECID из кэша.
        
        Args:
            secid: Идентификатор облигации (SECID) для поиска данных эмитента.
        
        Returns:
            Полные данные эмитента из ответа API MOEX (словарь со всеми полями)
            или None, если данные не найдены в кэше.
        """
        emitent_data = self._load_emitent_data()
        return emitent_data.get(secid)
    
    def extract_required_fields(self, emitent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлекает только необходимые поля из полного ответа API MOEX.
        
        Фильтрует данные эмитента, оставляя только поля, необходимые для работы
        приложения. Упрощает структуру данных для использования в других компонентах.
        
        Args:
            emitent_data: Полные данные эмитента из ответа API MOEX (словарь со всеми полями).
        
        Returns:
            Словарь с извлеченными полями:
            - is_traded: Флаг торговли облигацией
            - emitent_title: Название эмитента
            - emitent_inn: ИНН эмитента
            - type: Тип облигации
            - cci_rating_companies: Список рейтингов эмитента
        """
        return {
            "is_traded": emitent_data.get("is_traded"),
            "emitent_title": emitent_data.get("emitent_title"),
            "emitent_inn": emitent_data.get("emitent_inn"),
            "type": emitent_data.get("type"),
            "cci_rating_companies": emitent_data.get("cci_rating_companies"),
        }
    
    def fetch_emitent_from_moex(self, isin: str) -> Optional[Dict[str, Any]]:
        """Загружает данные эмитента из API MOEX по ISIN.
        
        Выполняет HTTP запрос к API Московской биржи для получения данных об эмитенте
        по ISIN коду облигации. Также загружает рейтинги эмитента по emitent_id.
        Сохраняет полный ответ API в файл используя SECID как ключ.
        
        Args:
            isin: ISIN код облигации для поиска данных эмитента.
        
        Returns:
            Полные данные эмитента из ответа API MOEX (словарь со всеми полями,
            включая рейтинги в поле cci_rating_companies) или None, если данные
            не найдены или произошла ошибка при загрузке.
        
        Note:
            После загрузки данных они сохраняются в кэш и файл bonds_emitent.json
            используя SECID облигации как ключ. Рейтинги эмитента загружаются
            отдельным запросом к API MOEX по emitent_id.
        """
        url = f"https://iss.moex.com/iss/securities.json?q={isin}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            print(f"Failed to fetch emitent data from MOEX: {exc}")
            return None
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            print(f"Invalid JSON response from MOEX: {exc}")
            return None
        
        # Parse MOEX response structure
        securities = payload.get("securities", {})
        columns = securities.get("columns", [])
        data = securities.get("data", [])
        
        if not data or len(data) == 0:
            return None
        
        # Find the row that matches the ISIN
        isin_idx = columns.index("isin") if "isin" in columns else None
        if isin_idx is None:
            return None
        
        # Find matching row by ISIN
        matching_row = None
        for row in data:
            if len(row) > isin_idx and row[isin_idx] == isin:
                matching_row = row
                break
        
        if matching_row is None:
            return None
        
        # Convert row to dict with all fields from MOEX response
        # This preserves the full JSON structure
        emitent_info = {}
        for idx, column_name in enumerate(columns):
            if idx < len(matching_row):
                emitent_info[column_name] = matching_row[idx]
        
        # Extract SECID from response to use as key
        secid_idx = columns.index("secid") if "secid" in columns else None
        if secid_idx is None or secid_idx >= len(matching_row):
            return None
        
        secid = matching_row[secid_idx]
        if not secid:
            return None
        
        # Extract emitent_id from emitent_info to fetch ratings
        emitent_id = emitent_info.get("emitent_id")
        if emitent_id is not None:
            try:
                emitent_id_int = int(emitent_id)
                print(f"[EMITENT SERVICE] Fetching ratings for emitent_id={emitent_id_int}")
                ratings = self._fetch_emitent_ratings(emitent_id_int)
                if ratings is not None:
                    emitent_info["cci_rating_companies"] = ratings
                    print(f"[EMITENT SERVICE] Added {len(ratings)} ratings to emitent data")
                else:
                    print(f"[EMITENT SERVICE] No ratings found for emitent_id={emitent_id_int}")
            except (ValueError, TypeError) as exc:
                print(f"[EMITENT SERVICE] Invalid emitent_id format: {emitent_id}, error: {exc}")
        
        # Save full MOEX response to cache and file using SECID as key
        if self._emitent_cache is None:
            self._emitent_cache = {}
        
        self._emitent_cache[secid] = emitent_info
        self._save_emitent_data()
        
        return emitent_info
    
    def _fetch_emitent_ratings(self, emitent_id: int) -> Optional[List[Dict[str, Any]]]:
        """Загружает рейтинги эмитента из API MOEX по emitent_id.
        
        Выполняет HTTP запрос к API Московской биржи для получения рейтингов эмитента
        по его идентификатору. Парсит ответ в формате JSON и извлекает данные из
        секции cci_rating_companies.
        
        Args:
            emitent_id: Идентификатор эмитента (целое число) для загрузки рейтингов.
        
        Returns:
            Список словарей с данными рейтингов эмитента из секции cci_rating_companies
            или None, если рейтинги не найдены или произошла ошибка при загрузке.
        
        Note:
            API MOEX возвращает данные в формате массива, где второй элемент содержит
            секцию cci_rating_companies с рейтингами.
        """
        url = f"https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}.json?iss.json=extended&iss.meta=off"
        
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30
            )
            response.raise_for_status()
            
            json_data = response.json()
            
            # Expected format: [{"charsetinfo": {...}}, {"cci_rating_companies": [...], ...}]
            if not isinstance(json_data, list) or len(json_data) < 2:
                print(f"[EMITENT SERVICE] Unexpected JSON structure for ratings - expected list with at least 2 elements")
                return None
            
            # Find the element with "cci_rating_companies" key
            ratings_data = None
            for item in json_data:
                if isinstance(item, dict) and "cci_rating_companies" in item:
                    ratings_data = item["cci_rating_companies"]
                    break
            
            if ratings_data is None:
                print(f"[EMITENT SERVICE] Could not find 'cci_rating_companies' in JSON response")
                return None
            
            if not isinstance(ratings_data, list):
                print(f"[EMITENT SERVICE] 'cci_rating_companies' is not a list")
                return None
            
            print(f"[EMITENT SERVICE] Found {len(ratings_data)} rating entries for emitent_id={emitent_id}")
            return ratings_data
            
        except requests.RequestException as exc:
            print(f"[EMITENT SERVICE] Failed to fetch emitent ratings from MOEX: {exc}")
            return None
        except Exception as exc:
            print(f"[EMITENT SERVICE] Error processing emitent ratings: {exc}")
            return None
    
    def get_or_fetch_emitent(self, secid: str, isin: str) -> Optional[Dict[str, Any]]:
        """Получает данные эмитента по SECID, загружая из MOEX если не найдены в кэше.
        
        Сначала пытается получить данные из кэша по SECID. Если данные не найдены,
        выполняет запрос к API MOEX используя ISIN для получения данных эмитента.
        
        Args:
            secid: Идентификатор облигации (SECID), используется как ключ в кэше.
            isin: ISIN код облигации, используется для запроса к API MOEX.
        
        Returns:
            Полные данные эмитента из ответа API MOEX (словарь со всеми полями)
            или None, если данные не найдены ни в кэше, ни в API MOEX.
        """
        # First try to get from cache by SECID
        emitent_data = self.get_emitent_by_secid(secid)
        if emitent_data is not None:
            return emitent_data
        
        # If not found, fetch from MOEX using ISIN
        emitent_data = self.fetch_emitent_from_moex(isin)
        return emitent_data
    
    async def get_isin_by_secid(self, secid: str) -> Optional[str]:
        """Получает ISIN код облигации по SECID из данных облигаций.
        
        Загружает детальную информацию об облигации из DataLoader и извлекает
        ISIN код из секции securities.
        
        Args:
            secid: Идентификатор облигации (SECID) для поиска ISIN.
        
        Returns:
            ISIN код облигации или None, если облигация не найдена или ISIN отсутствует.
        """
        loader = get_data_loader()
        details = await loader.get_bond_details()
        
        if secid not in details:
            return None
        
        bond_data = details[secid]
        securities = bond_data.get("securities", {})
        return securities.get("ISIN")
    
    def _fetch_emitent_from_moex_by_isin(self, isin: str) -> Optional[Dict[str, Any]]:
        """Загружает данные эмитента из API MOEX по ISIN без сохранения.
        
        Выполняет HTTP запрос к API Московской биржи для получения данных об эмитенте
        по ISIN коду облигации. Также загружает рейтинги эмитента по emitent_id.
        Не сохраняет данные в файл (используется для массового обновления).
        
        Args:
            isin: ISIN код облигации для поиска данных эмитента.
        
        Returns:
            Полные данные эмитента из ответа API MOEX (словарь со всеми полями,
            включая рейтинги в поле cci_rating_companies) или None, если данные
            не найдены или произошла ошибка при загрузке.
        
        Note:
            В отличие от fetch_emitent_from_moex(), этот метод не сохраняет данные
            в файл. Используется для массового обновления данных, когда сохранение
            выполняется один раз в конце процесса.
        """
        url = f"https://iss.moex.com/iss/securities.json?q={isin}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            print(f"Failed to fetch emitent data from MOEX: {exc}")
            return None
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            print(f"Invalid JSON response from MOEX: {exc}")
            return None
        
        # Parse MOEX response structure
        securities = payload.get("securities", {})
        columns = securities.get("columns", [])
        data = securities.get("data", [])
        
        if not data or len(data) == 0:
            return None
        
        # Find the row that matches the ISIN
        isin_idx = columns.index("isin") if "isin" in columns else None
        if isin_idx is None:
            return None
        
        # Find matching row by ISIN
        matching_row = None
        for row in data:
            if len(row) > isin_idx and row[isin_idx] == isin:
                matching_row = row
                break
        
        if matching_row is None:
            return None
        
        # Convert row to dict with all fields from MOEX response
        emitent_info = {}
        for idx, column_name in enumerate(columns):
            if idx < len(matching_row):
                emitent_info[column_name] = matching_row[idx]
        
        # Extract emitent_id from emitent_info to fetch ratings
        emitent_id = emitent_info.get("emitent_id")
        if emitent_id is not None:
            try:
                emitent_id_int = int(emitent_id)
                print(f"[EMITENT SERVICE] Fetching ratings for emitent_id={emitent_id_int}")
                ratings = self._fetch_emitent_ratings(emitent_id_int)
                if ratings is not None:
                    emitent_info["cci_rating_companies"] = ratings
                    print(f"[EMITENT SERVICE] Added {len(ratings)} ratings to emitent data")
                else:
                    print(f"[EMITENT SERVICE] No ratings found for emitent_id={emitent_id_int}")
            except (ValueError, TypeError) as exc:
                print(f"[EMITENT SERVICE] Invalid emitent_id format: {emitent_id}, error: {exc}")
        
        return emitent_info
    
    def refresh_all_emitents(self, bonds_details: Dict[str, Dict]) -> Dict[str, int]:
        """Обновляет данные эмитентов для всех облигаций из bonds.json.
        
        Выполняет массовое обновление данных об эмитентах для всех облигаций.
        Итерируется по всем облигациям, извлекает SECID и ISIN, и загружает данные
        эмитента из API MOEX для каждой облигации. Сохраняет данные используя SECID
        облигации как ключ.
        
        Args:
            bonds_details: Словарь с детальной информацией об облигациях, где ключ -
                SECID облигации, значение - словарь с данными облигации (должен содержать
                секцию "securities" с полем "ISIN").
        
        Returns:
            Словарь со статистикой обновления:
            - total: Общее количество облигаций для обработки
            - updated: Количество успешно обновленных записей
            - errors: Количество ошибок при обновлении
            - skipped: Количество пропущенных облигаций (отсутствует ISIN)
        
        Note:
            Данные сохраняются в файл один раз в конце процесса обновления для всех
            успешно загруженных записей. Рейтинги эмитентов загружаются автоматически
            для каждой облигации при наличии emitent_id.
        """
        total_bonds = len(bonds_details)
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        # Ensure cache is loaded
        self._load_emitent_data()
        
        for secid, bond_data in bonds_details.items():
            try:
                # Extract ISIN from bond data
                securities = bond_data.get("securities", {})
                isin = securities.get("ISIN")
                
                if not isin:
                    print(f"[EMITENT REFRESH] Bond {secid}: Skipping - missing ISIN")
                    skipped_count += 1
                    continue
                
                # Fetch emitent data from MOEX (without saving)
                emitent_data = self._fetch_emitent_from_moex_by_isin(isin)
                if emitent_data is not None:
                    # Ratings are already included in emitent_data by _fetch_emitent_from_moex_by_isin
                    # Save data using bond SECID as key (not MOEX SECID)
                    if self._emitent_cache is None:
                        self._emitent_cache = {}
                    self._emitent_cache[secid] = emitent_data
                    updated_count += 1
                    ratings_count = len(emitent_data.get("cci_rating_companies", []))
                    if ratings_count > 0:
                        print(f"[EMITENT REFRESH] Bond {secid}: Successfully updated with {ratings_count} ratings")
                    else:
                        print(f"[EMITENT REFRESH] Bond {secid}: Successfully updated (no ratings)")
                else:
                    error_count += 1
                    print(f"[EMITENT REFRESH] Bond {secid}: Failed to fetch from MOEX")
                    
            except Exception as exc:
                error_count += 1
                print(f"[EMITENT REFRESH] Bond {secid}: ERROR - {type(exc).__name__}: {str(exc)}")
                continue
        
        # Save all updated data once at the end
        if updated_count > 0:
            self._save_emitent_data()
            print(f"[EMITENT REFRESH] Saved {updated_count} updated emitent records to file")
        
        return {
            "total": total_bonds,
            "updated": updated_count,
            "errors": error_count,
            "skipped": skipped_count
        }


# Singleton instance
_emitent_service: Optional[EmitentService] = None


def init_emitent_service(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр сервиса эмитентов.
    
    Создает глобальный экземпляр EmitentService с указанной директорией данных.
    Должен быть вызван перед использованием get_emitent_service().
    
    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _emitent_service
    _emitent_service = EmitentService(data_dir)


def get_emitent_service() -> EmitentService:
    """Получает singleton экземпляр сервиса эмитентов.
    
    Returns:
        Экземпляр EmitentService для работы с данными эмитентов.
    
    Raises:
        RuntimeError: Если сервис не был инициализирован через init_emitent_service().
    """
    if _emitent_service is None:
        raise RuntimeError("Emitent service not initialized")
    return _emitent_service

