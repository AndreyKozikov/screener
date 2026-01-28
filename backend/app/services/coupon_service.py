"""Сервис для работы с данными о купонах облигаций из API MOEX.

Этот модуль содержит класс CouponService для загрузки, кэширования и управления
данными о купонах облигаций из API Московской биржи. Данные сохраняются в JSON файл
и обновляются при необходимости.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson

COUPONS_DATA_FILE: Path = Path(__file__).parent.parent / "data" / "coupons_data.json"
"""Путь к файлу для хранения данных о купонах облигаций."""


class CouponService:
    """Сервис для работы с данными о купонах облигаций из API MOEX.
    
    Класс обеспечивает загрузку данных о купонах облигаций из API Московской биржи,
    кэширование данных в JSON файл и управление обновлением данных. Поддерживает
    загрузку данных для одной облигации или пакетную загрузку для нескольких облигаций.
    
    Attributes:
        STALE_DAYS: Количество дней, после которых данные считаются устаревшими
            и требуют обновления (по умолчанию 14 дней).
        data_file: Путь к файлу для хранения данных о купонах.
    """
    
    STALE_DAYS: int = 14
    """Количество дней, после которых данные считаются устаревшими."""
    
    def __init__(self, data_file: Path = COUPONS_DATA_FILE):
        """Инициализирует сервис для работы с купонами.
        
        Args:
            data_file: Путь к файлу для хранения данных о купонах.
                По умолчанию используется COUPONS_DATA_FILE.
        """
        self.data_file = data_file
        self._ensure_data_file_exists()
    
    def _ensure_data_file_exists(self) -> None:
        """Создает файл данных о купонах, если он не существует.
        
        Создает файл с начальной структурой {"bonds": {}}, если файл отсутствует.
        """
        if not self.data_file.exists():
            initial_data = {
                "bonds": {}
            }
            self._write_data(initial_data)
    
    def _read_data(self) -> Dict:
        """Читает данные о купонах из JSON файла.
        
        Загружает данные из файла coupons_data.json. Обрабатывает ошибки чтения
        и поврежденные файлы, создавая резервную копию при необходимости.
        
        Returns:
            Словарь с данными о купонах. Структура: {"bonds": {SECID: {...}}}.
            Если файл не существует или поврежден, возвращает {"bonds": {}}.
        
        Note:
            При обнаружении поврежденного файла создается резервная копия с расширением
            .json.corrupted, и возвращается пустая структура, что приведет к обновлению
            данных из API MOEX.
        """
        if not self.data_file.exists():
            return {"bonds": {}}
        
        try:
            with open(self.data_file, 'rb') as f:
                raw_data = f.read()
                return orjson.loads(raw_data)
        except (orjson.JSONDecodeError, UnicodeDecodeError) as exc:
            # If file is corrupted, log error and return empty structure
            # This will force refresh from MOEX API
            print(f"[КУПОНЫ] ВНИМАНИЕ: Файл {self.data_file} поврежден (ошибка: {type(exc).__name__}: {exc})")
            print(f"[КУПОНЫ] Файл будет пересоздан при следующем обновлении данных")
            # Try to backup corrupted file
            try:
                backup_path = self.data_file.with_suffix('.json.corrupted')
                if not backup_path.exists():
                    import shutil
                    shutil.copy2(self.data_file, backup_path)
                    print(f"[КУПОНЫ] Создана резервная копия поврежденного файла: {backup_path}")
            except Exception:
                pass  # Ignore backup errors
            return {"bonds": {}}
    
    def _write_data(self, data: Dict) -> None:
        """Записывает данные о купонах в JSON файл.
        
        Сохраняет данные в файл coupons_data.json с форматированием (отступы и
        перенос строки). Перед записью очищает строковые значения для обеспечения
        валидной UTF-8 кодировки.
        
        Args:
            data: Словарь с данными о купонах для сохранения.
        
        Note:
            Если сериализация не удается, выполняется дополнительная очистка данных
            и повторная попытка записи.
        """
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean data before serialization to ensure valid UTF-8
        cleaned_data = self._clean_string_value(data)
        
        try:
            serialized = orjson.dumps(
                cleaned_data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
            )
            self.data_file.write_bytes(serialized)
        except (TypeError, ValueError) as exc:
            # If serialization fails, try to clean data more aggressively
            print(f"[КУПОНЫ] ВНИМАНИЕ: Ошибка при сериализации данных: {exc}")
            print(f"[КУПОНЫ] Попытка дополнительной очистки данных...")
            # Additional cleaning pass
            cleaned_data = self._clean_string_value(cleaned_data)
            serialized = orjson.dumps(
                cleaned_data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
            )
            self.data_file.write_bytes(serialized)
    
    def _is_data_stale(self, last_updated: str) -> bool:
        """Проверяет, устарели ли данные.
        
        Определяет, превышает ли возраст данных значение STALE_DAYS дней.
        
        Args:
            last_updated: Строка с датой последнего обновления в формате YYYY-MM-DD.
        
        Returns:
            True если данные старше STALE_DAYS дней, False в противном случае.
            Если дата некорректна или не может быть распознана, возвращает True
            (данные считаются устаревшими).
        """
        try:
            last_date = datetime.strptime(last_updated, "%Y-%m-%d").date()
            days_ago = (date.today() - last_date).days
            return days_ago > self.STALE_DAYS
        except (ValueError, TypeError):
            return True
    
    
    def _download_coupons_from_moex(self, secid: str) -> Dict:
        """Загружает данные о купонах облигации из API MOEX.
        
        Выполняет HTTP запрос к API Московской биржи для получения данных о купонах,
        амортизациях и офертах облигации. Парсит ответ в формате JSON и возвращает
        структурированные данные.
        
        Args:
            secid: Идентификатор облигации (SECID) для загрузки данных.
        
        Returns:
            Словарь с данными облигации, содержащий:
            - coupons: Список словарей с данными купонов
            - amortizations: Список словарей с данными амортизаций (создается из первого купона)
            - offers: Список словарей с данными оферт (пустой массив, так как API не возвращает оферты)
        
        Raises:
            RuntimeError: Если не удалось загрузить данные (сетевая ошибка, таймаут)
                или если формат ответа API неожиданный.
        
        Note:
            Новый формат API возвращает массив: [{"charsetinfo": {...}}, {"coupons": [...]}].
            Только купоны возвращаются API, амортизации и оферты пустые.
            Минимальная запись амортизации создается из данных первого купона.
        """
        url = f"https://iss.moex.com/iss/securities/{secid}/bondization.json?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&limit=unlimited"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            raise RuntimeError(f"Failed to download coupons data for {secid}: {exc}") from exc
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            raise RuntimeError(f"Received invalid JSON for {secid}: {exc}") from exc
        
        # Parse the response structure
        result = {
            "amortizations": [],
            "coupons": [],
            "offers": []
        }
        
        # New API format: payload is an array, second element contains coupons
        # Format: [{"charsetinfo": {"name": "utf-8"}}, {"coupons": [...]}]
        if not isinstance(payload, list) or len(payload) < 2:
            raise RuntimeError(f"Unexpected API response format for {secid}: expected array with at least 2 elements")
        
        # Get coupons array from second element
        coupons_data = payload[1].get("coupons", [])
        if not isinstance(coupons_data, list):
            raise RuntimeError(f"Unexpected coupons format for {secid}: expected array, got {type(coupons_data).__name__}")
        
        # Parse coupons - they come as objects already in new API format
        first_coupon_raw = None
        for coupon_dict in coupons_data:
            # Create a copy to avoid modifying original data, then clean string values
            coupon_dict_copy = coupon_dict.copy() if isinstance(coupon_dict, dict) else coupon_dict
            coupon_dict_cleaned = self._clean_string_value(coupon_dict_copy)
            result["coupons"].append(coupon_dict_cleaned)
            # Save first coupon raw data (before cleaning duplicate fields) for amortization creation
            if first_coupon_raw is None:
                first_coupon_raw = coupon_dict_cleaned
        
        # Create a minimal amortization entry from first coupon data
        # Use first coupon raw data (already cleaned for UTF-8, but before removing duplicate fields)
        if first_coupon_raw is not None:
            # Create amortization entry with common fields from coupon
            amort_entry = {
                "isin": first_coupon_raw.get("isin"),
                "name": first_coupon_raw.get("name"),
                "issuevalue": first_coupon_raw.get("issuevalue"),
                "secid": first_coupon_raw.get("secid") or secid,
                "primary_boardid": first_coupon_raw.get("primary_boardid"),
                "facevalue": first_coupon_raw.get("facevalue"),
                "initialfacevalue": first_coupon_raw.get("initialfacevalue"),
                "faceunit": first_coupon_raw.get("faceunit"),
            }
            # Clean and add to result (already cleaned, but double-check)
            amort_entry = self._clean_string_value(amort_entry)
            result["amortizations"].append(amort_entry)
        
        # Offers are not returned by new API, leaving empty array
        
        return result
    
    def get_coupons(self, secid: str, force_refresh: bool = False) -> Dict:
        """Получает данные о купонах для конкретной облигации.
        
        Загружает данные о купонах облигации из кэша (JSON файл) или из API MOEX,
        если данные отсутствуют, устарели или запрошено принудительное обновление.
        Очищает кэши загрузчиков данных после обновления.
        
        Args:
            secid: Идентификатор облигации (SECID) для получения данных.
            force_refresh: Если True, принудительно загружает данные из API MOEX,
                игнорируя кэш. По умолчанию False.
        
        Returns:
            Словарь с данными облигации, содержащий:
            - last_updated: Дата последнего обновления в формате YYYY-MM-DD
            - amortizations: Список словарей с данными амортизаций
            - coupons: Список словарей с данными купонов (с удаленными дублирующимися полями)
            - offers: Список словарей с данными оферт
        
        Raises:
            RuntimeError: Если не удалось загрузить данные из API и нет кэшированных данных.
        
        Note:
            После обновления данных очищаются кэши CouponLoader и DataLoader для
            обеспечения актуальности данных в других компонентах системы.
        """
        data = self._read_data()
        bonds = data.get("bonds", {})
        
        # Check if data exists and is not stale
        if secid in bonds and not force_refresh:
            bond_data = bonds[secid]
            last_updated = bond_data.get("last_updated", "")
            
            if last_updated and not self._is_data_stale(last_updated):
                # Clean cached data to ensure valid UTF-8 (in case it was saved before fix)
                try:
                    bond_data = self._clean_string_value(bond_data)
                except Exception as exc:
                    # If cleaning fails, force refresh by breaking out of this block
                    print(f"[КУПОНЫ] ВНИМАНИЕ: Не удалось очистить кэшированные данные для {secid}: {exc}")
                    print(f"[КУПОНЫ] Будет выполнена загрузка свежих данных с MOEX")
                    # bond_data will be None, so we'll skip this block and download fresh data
                    bond_data = None
                
                if bond_data:
                    coupons = bond_data.get("coupons", [])
                    
                    # Clean duplicate fields from coupons (for old data structure)
                    bond_data["coupons"] = [self._clean_coupon_fields(c) for c in coupons]
                    
                    return bond_data
        
        # Download fresh data
        try:
            fresh_data = self._download_coupons_from_moex(secid)
        except Exception as exc:
            # If download fails and we have cached data, return it (with cleaned coupons)
            if secid in bonds:
                cached_data = bonds[secid].copy()
                cached_coupons = cached_data.get("coupons", [])
                cached_data["coupons"] = [self._clean_coupon_fields(c) for c in cached_coupons]
                return cached_data
            raise exc
        
        # Data is already cleaned in _download_coupons_from_moex, but clean again to be safe
        # Remove duplicate fields from coupons using helper method
        fresh_data["coupons"] = [self._clean_coupon_fields(c) for c in fresh_data["coupons"]]
        
        # Save to file (data is already cleaned)
        bond_entry = {
            "last_updated": date.today().isoformat(),
            "amortizations": fresh_data["amortizations"],
            "coupons": fresh_data["coupons"],
            "offers": fresh_data["offers"]
        }
        
        bonds[secid] = bond_entry
        data["bonds"] = bonds
        self._write_data(data)
        
        # Clear CouponLoader cache so it picks up the new data
        from app.services.coupon_loader import get_coupon_loader
        coupon_loader = get_coupon_loader()
        if coupon_loader is not None:
            coupon_loader.clear_cache()
        
        # Clear DataLoader cache so bonds list is reloaded with new coupon data
        from app.services.data_loader import get_data_loader
        try:
            data_loader = get_data_loader()
            data_loader.clear_bonds_cache()  # Clear bonds cache to force reload
        except RuntimeError:
            # DataLoader not initialized yet, that's ok
            pass
        
        return bond_entry
    
    def _clean_string_value(self, value: any) -> any:
        """Очищает строковые значения для обеспечения валидной UTF-8 кодировки.
        
        Рекурсивно обрабатывает структуры данных (словари, списки) и очищает все
        строковые значения, удаляя суррогатные пары, которые вызывают ошибки
        кодировки UTF-8.
        
        Args:
            value: Значение для очистки. Может быть строкой, словарем, списком
                или другим типом данных. Для словарей и списков выполняется
                рекурсивная обработка всех элементов.
        
        Returns:
            Очищенное значение с валидными UTF-8 строками. Для словарей и списков
            возвращается новая структура с очищенными значениями. Для других типов
            (int, float, bool, None) возвращается исходное значение без изменений.
        """
        if value is None:
            return None
        elif isinstance(value, str):
            # Remove surrogate pairs by encoding/decoding with error handling
            try:
                # Try to encode and decode to validate UTF-8
                value.encode('utf-8').decode('utf-8')
                return value
            except (UnicodeEncodeError, UnicodeDecodeError):
                # If encoding fails, remove invalid characters
                # Replace surrogates with replacement character
                cleaned = value.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                return cleaned
        elif isinstance(value, dict):
            return {k: self._clean_string_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._clean_string_value(item) for item in value]
        else:
            # For other types (int, float, bool, etc.), return as-is
            return value
    
    def _clean_coupon_fields(self, coupon: Dict) -> Dict:
        """Удаляет дублирующиеся поля из купона.
        
        Удаляет из словаря купона поля, которые дублируются и должны находиться
        в секции амортизаций, а не в секции купонов.
        
        Args:
            coupon: Словарь с данными купона для очистки.
        
        Returns:
            Очищенный словарь купона без дублирующихся полей. Удаляются поля:
            isin, name, issuevalue, primary_boardid, secid.
        """
        # Fields to remove from coupons (these are duplicated and moved to amortizations)
        fields_to_remove = ["isin", "name", "issuevalue", "primary_boardid", "secid"]
        cleaned = {k: v for k, v in coupon.items() if k not in fields_to_remove}
        return cleaned
    
    def get_coupons_only(self, secid: str, force_refresh: bool = False) -> List[Dict]:
        """Получает только данные о купонах (для отображения на фронтенде).
        
        Загружает данные облигации и возвращает только список купонов без других
        данных (амортизации, оферты). Удобно для использования в API endpoints,
        которые возвращают только купоны.
        
        Args:
            secid: Идентификатор облигации (SECID) для получения купонов.
            force_refresh: Если True, принудительно загружает данные из API MOEX.
                По умолчанию False.
        
        Returns:
            Список словарей с данными купонов. Каждый словарь содержит данные одного
            купона с удаленными дублирующимися полями (isin, name, issuevalue, и т.д.).
        """
        bond_data = self.get_coupons(secid, force_refresh)
        coupons = bond_data.get("coupons", [])
        # Clean old fields from coupons for backward compatibility with old data structure
        return [self._clean_coupon_fields(c) for c in coupons]
    
    def get_coupons_batch(self, secids: List[str], use_db: bool = True) -> Dict[str, Dict]:
        """Получает данные о купонах для нескольких облигаций.
        
        Выполняет пакетную загрузку данных о купонах для списка облигаций.
        Поддерживает загрузку из базы данных (приоритет) или из JSON файла (fallback).
        
        Args:
            secids: Список идентификаторов облигаций (SECID) для получения данных.
            use_db: Если True, пытается получить купоны из базы данных сначала,
                затем переключается на JSON файл при ошибке. Если False, использует
                только JSON файл. По умолчанию True.
        
        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с данными:
            {
                "coupons": [...],  # Список словарей с данными купонов
                "coupon_type": "FIX" | "FLOAT" | None,  # Тип купона из амортизаций
                "amortizations": [...]  # Список словарей с данными амортизаций
            }
            Если для облигации нет данных, возвращается структура с пустыми списками.
        
        Note:
            При использовании базы данных (use_db=True) купоны загружаются из таблицы
            coupons, а тип купона и амортизации - из JSON файла (кэш CouponService).
            При ошибке доступа к БД выполняется автоматический переход на JSON файл.
        """
        if not secids:
            return {}
        
        result: Dict[str, Dict] = {}
        
        # Try to get coupons from database if use_db is True
        if use_db:
            try:
                from app.repository.db_coupon import DBCoupon
                db_coupon = DBCoupon()
                db_coupons = db_coupon.fetch_coupons_raw(secids=secids)
                
                # Group coupons by secid
                coupons_by_secid: Dict[str, List[Dict]] = {}
                for coupon_row in db_coupons:
                    secid = coupon_row.get("secid")
                    if secid:
                        if secid not in coupons_by_secid:
                            coupons_by_secid[secid] = []
                        # Clean coupon fields (remove secid from coupon data as it's in the key)
                        cleaned_coupon = {k: v for k, v in coupon_row.items() if k != "secid"}
                        coupons_by_secid[secid].append(self._clean_coupon_fields(cleaned_coupon))
                
                # Get coupon_type from JSON file for each secid
                data = self._read_data()
                bonds = data.get("bonds", {})
                
                for secid in secids:
                    coupons = coupons_by_secid.get(secid, [])
                    coupon_type = None
                    amortizations = []
                    
                    # Try to get coupon_type from cached data
                    if secid in bonds:
                        bond_data = bonds[secid]
                        amortizations_data = bond_data.get("amortizations", [])
                        if amortizations_data and len(amortizations_data) > 0:
                            coupon_type = amortizations_data[0].get("coupon_type")
                            amortizations = amortizations_data
                    
                    result[secid] = {
                        "coupons": coupons,
                        "coupon_type": coupon_type,
                        "amortizations": amortizations
                    }
                
                # Return data from DB (even if some coupons are empty)
                # We got data from DB for all requested secids (some may have empty coupons, which is valid)
                return result
            except Exception as exc:
                # If DB access fails, fallback to JSON file
                print(f"[КУПОНЫ] ВНИМАНИЕ: Не удалось получить купоны из БД: {exc}")
                print(f"[КУПОНЫ] Переключение на загрузку из JSON файла")
        
        # Fallback: get coupons from JSON file (coupon_service cache)
        data = self._read_data()
        bonds = data.get("bonds", {})
        
        for secid in secids:
            if secid in bonds:
                bond_data = bonds[secid].copy()
                coupons_data = bond_data.get("coupons", [])
                amortizations = bond_data.get("amortizations", [])
                
                # Clean duplicate fields from coupons
                cleaned_coupons = [self._clean_coupon_fields(c) for c in coupons_data]
                
                # Get coupon_type from amortizations
                coupon_type = None
                if amortizations and len(amortizations) > 0:
                    coupon_type = amortizations[0].get("coupon_type")
                
                result[secid] = {
                    "coupons": cleaned_coupons,
                    "coupon_type": coupon_type,
                    "amortizations": amortizations
                }
            else:
                # No data for this secid
                result[secid] = {
                    "coupons": [],
                    "coupon_type": None,
                    "amortizations": []
                }
        
        return result


# Singleton instance
_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    """Получает singleton экземпляр сервиса купонов.
    
    Создает глобальный экземпляр CouponService при первом вызове и возвращает его
    при последующих вызовах (singleton pattern).
    
    Returns:
        Экземпляр CouponService для работы с данными о купонах.
    """
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service

