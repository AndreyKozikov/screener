"""Загрузчик данных об облигациях с кэшированием в памяти.

Модуль содержит класс DataLoader: загрузка payload с MOEX, заполнение кэша
в памяти (без записи bonds.json), загрузка рейтингов и метаданных из файлов/БД.
Данные облигаций существуют в памяти во время транзакции и в БД после миграции.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.bond import BondListItem
from app.repository.db.bond_ratings_repository import BondRatingsRepository
from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.files.file_storage import FileStorage
from app.utils.rating_utils import get_rating_index
from app.services.moex_client import MoexClient
from app.utils.logger import get_data_update_logger


class DataLoader:
    """Загрузчик данных об облигациях с кэшированием в памяти.

    Кэш заполняется из payload (ответ MOEX), без записи bonds.json. Рейтинги
    загружаются из БД (bond_ratings), типы облигаций — из БД (emitents).

    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
        _moex_client: Клиент для загрузки данных с MOEX.
        _file_storage: Хранилище для чтения/записи JSON файлов.
        _bonds_cache: Кэш списка облигаций (BondListItem).
        _details_cache: Кэш детальной информации об облигациях.
        _columns_cache: Кэш маппингов колонок (поле -> отображаемое имя).
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
        self._bond_ratings_repo = BondRatingsRepository()
        self._bonds_cache: Optional[List[BondListItem]] = None
        self._details_cache: Optional[Dict[str, Dict]] = None
        self._columns_cache: Optional[Dict[str, str]] = None

    async def get_bonds(self) -> List[BondListItem]:
        """Получает список всех облигаций (с кэшированием).

        Возвращает кэш списка облигаций. Если кэш пуст (обновление ещё не выполнялось),
        возвращает пустой список без попытки чтения с диска.

        Returns:
            Список объектов BondListItem с данными облигаций. Облигации с режимом
            торгов SPOB исключаются из списка. Пустой список, если кэш не заполнен.
        """
        if self._bonds_cache is None:
            return []
        return self._bonds_cache

    async def get_bond_details(self) -> Dict[str, Dict]:
        """Получает детальную информацию об облигациях (с кэшированием).

        Возвращает кэш детальной информации. Если кэш пуст (обновление ещё не выполнялось),
        возвращает пустой словарь без попытки чтения с диска.

        Returns:
            Словарь, где ключ - SECID облигации, значение - словарь с детальной
            информацией (securities, marketdata, marketdata_yields).
            Пустой словарь, если кэш не заполнен.
        """
        if self._details_cache is None:
            return {}
        return self._details_cache

    def get_bond_details_sync(self) -> Dict[str, Dict]:
        """Синхронно возвращает детальную информацию об облигациях (с кэшированием).

        Используется в пайплайне обновления эмитентов. Если кэш пуст, возвращает
        пустой словарь без попытки чтения с диска.

        Returns:
            Словарь SECID -> детальные данные облигации (securities, marketdata, marketdata_yields).
        """
        if self._details_cache is None:
            return {}
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

    def fetch_bonds_payload(self, source_url: str) -> Dict[str, Any]:
        """Загружает JSON-ответ об облигациях с MOEX по указанному URL.

        Args:
            source_url: URL для загрузки (например, MOEX bonds API).

        Returns:
            Словарь с секциями securities, marketdata, marketdata_yields.

        Raises:
            RuntimeError: При сетевой ошибке или некорректном JSON.
        """
        return self._moex_client.fetch_bonds_json(source_url)

    def refresh_bonds_dataset(self, payload: Dict[str, Any], source_url: Optional[str] = None) -> Dict[str, int]:
        """Обновляет кэш облигаций из переданного payload (ответ MOEX).

        Записей на диск не производится. Данные существуют только в памяти (кэш)
        и в БД после миграции.

        Args:
            payload: JSON-ответ MOEX с секциями securities, marketdata, marketdata_yields.
            source_url: Опциональный URL источника для логирования.

        Returns:
            Словарь с количеством записей: securities, marketdata, marketdata_yields.

        Raises:
            RuntimeError: Если payload некорректен или не содержит ожидаемых секций.
        """
        logger = get_data_update_logger()
        logger.info("[REFRESH BONDS] Starting bonds dataset refresh from payload (source_url=%s)", source_url)

        self._bonds_cache = None
        self._details_cache = None
        self._populate_cache_from_payload(payload)
        logger.info("[REFRESH BONDS] Cache populated successfully")

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

    def _populate_cache_from_payload(self, payload: Dict[str, Any]) -> None:
        """Заполняет _bonds_cache и _details_cache из JSON-ответа MOEX.

        Объединяет секции securities, marketdata и marketdata_yields по SECID,
        подгружает рейтинги из БД (bond_ratings) и типы облигаций из БД (emitents).

        Args:
            payload: Словарь с ключами securities, marketdata, marketdata_yields
                (формат ответа MOEX API).
        """
        logger = get_data_update_logger()
        logger.info("[POPULATE CACHE] Populating bonds cache from payload")

        securities = payload.get("securities", {})
        sec_columns = securities.get("columns", [])
        sec_data = securities.get("data", [])
        logger.info("[POPULATE CACHE] Parsed %s securities records", len(sec_data))

        marketdata = payload.get("marketdata", {})
        md_columns = marketdata.get("columns", [])
        md_data = marketdata.get("data", [])
        logger.info("[POPULATE CACHE] Parsed %s marketdata records", len(md_data))

        yields = payload.get("marketdata_yields", {})
        yields_columns = yields.get("columns", [])
        yields_data = yields.get("data", [])
        logger.info("[POPULATE CACHE] Parsed %s yields records", len(yields_data))

        bonds_list: List[BondListItem] = []
        details_map: Dict[str, Dict] = {}
        skipped_spob_count = 0

        for row in sec_data:
            bond_dict = dict(zip(sec_columns, row))

            boardid = bond_dict.get("BOARDID")
            if boardid and boardid.strip().upper() == "SPOB":
                skipped_spob_count += 1
                continue

            for date_field in [
                "NEXTCOUPON", "MATDATE", "BUYBACKDATE", "PREVDATE",
                "OFFERDATE", "SETTLEDATE", "CALLOPTIONDATE",
                "PUTOPTIONDATE", "DATEYIELDFROMISSUER",
            ]:
                if date_field in bond_dict and bond_dict[date_field]:
                    bond_dict[date_field] = self._parse_date(bond_dict[date_field])

            try:
                bondtype43_value = bond_dict.get("BONDTYPE")
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
                    "DURATION": None,
                    "DURATIONWAPRICE": None,
                    "CURRENCYID": bond_dict.get("CURRENCYID"),
                    "LISTLEVEL": self._parse_int(bond_dict.get("LISTLEVEL")),
                    "BONDTYPE43": bondtype43_value,
                }
                list_item = BondListItem(**list_item_data)
                bonds_list.append(list_item)
            except Exception as e:
                logger.warning("Error parsing bond %s: %s", bond_dict.get("SECID"), e)
                continue

            secid = bond_dict.get("SECID")
            if secid:
                if "BONDTYPE" in bond_dict:
                    bond_dict["BONDTYPE43"] = bond_dict.get("BONDTYPE")
                details_map[secid] = {
                    "securities": bond_dict,
                    "marketdata": {},
                    "marketdata_yields": [],
                }

        for row in md_data:
            md_dict = dict(zip(md_columns, row))
            secid = md_dict.get("SECID")
            boardid = md_dict.get("BOARDID")

            if secid and secid in details_map:
                details_map[secid]["marketdata"] = md_dict
                if secid:
                    matched_bond = None
                    if boardid:
                        for bond in bonds_list:
                            if bond.SECID == secid and bond.BOARDID == boardid:
                                matched_bond = bond
                                break
                    if matched_bond is None:
                        for bond in bonds_list:
                            if bond.SECID == secid:
                                matched_bond = bond
                                break
                    if matched_bond:
                        if md_dict.get("TRADINGSTATUS"):
                            matched_bond.TRADINGSTATUS = md_dict.get("TRADINGSTATUS")
                        duration_raw = md_dict.get("DURATION")
                        if "DURATION" in md_dict:
                            try:
                                if duration_raw is None:
                                    matched_bond.DURATION = None
                                elif isinstance(duration_raw, (int, float)):
                                    matched_bond.DURATION = float(duration_raw)
                                elif isinstance(duration_raw, str):
                                    duration_str = duration_raw.strip()
                                    if duration_str and duration_str.lower() not in ("", "nan", "none", "null", "n/a"):
                                        try:
                                            matched_bond.DURATION = float(duration_str)
                                        except (ValueError, TypeError):
                                            matched_bond.DURATION = None
                                    else:
                                        matched_bond.DURATION = None
                                else:
                                    matched_bond.DURATION = None
                            except (ValueError, TypeError, AttributeError):
                                matched_bond.DURATION = None

        for row in yields_data:
            yields_dict = dict(zip(yields_columns, row))
            secid = yields_dict.get("SECID")
            if secid and secid in details_map:
                details_map[secid]["marketdata_yields"].append(yields_dict)
                durationwaprice = yields_dict.get("DURATIONWAPRICE")
                if durationwaprice is not None:
                    for bond in bonds_list:
                        if bond.SECID == secid:
                            if bond.DURATIONWAPRICE is None:
                                bond.DURATIONWAPRICE = durationwaprice
                            break

        logger.info("[POPULATE CACHE] Loading ratings data")
        ratings_map = self._load_ratings_map()
        self._add_ratings_to_bonds(bonds_list, ratings_map)
        for secid, rating_info in ratings_map.items():
            if secid in details_map:
                all_ratings = rating_info.get("all_ratings", [])
                details_map[secid]["securities"]["RATINGS"] = all_ratings
                worst_rating = self._get_worst_rating(all_ratings)
                if worst_rating:
                    details_map[secid]["securities"]["RATING_AGENCY"] = worst_rating.get("agency_name_short_ru", "").strip()
                    details_map[secid]["securities"]["RATING_LEVEL"] = worst_rating.get("rating_level_name_short_ru", "").strip()

        logger.info("[POPULATE CACHE] Loading bond types data")
        bondtype_map = self._load_bondtype_map()
        self._add_bondtypes_to_bonds(bonds_list, bondtype_map)
        for secid, bondtype in bondtype_map.items():
            if secid in details_map:
                details_map[secid]["securities"]["BONDTYPE"] = bondtype

        self._bonds_cache = bonds_list
        self._details_cache = details_map
        logger.info(
            "[POPULATE CACHE] Loaded %s bonds, %s details, %s ratings, %s bond types",
            len(bonds_list), len(details_map), len(ratings_map), len(bondtype_map),
        )
        if skipped_spob_count > 0:
            logger.info("[POPULATE CACHE] Skipped %s bonds with trading mode SPOB", skipped_spob_count)
    
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
    
    def clear_bonds_cache(self) -> None:
        """Очищает кэш облигаций для принудительной перезагрузки.
        
        Сбрасывает кэши списка облигаций и детальной информации. Используется
        после обновления данных о купонах для принудительной перезагрузки данных
        с актуальными значениями купонов.
        """
        self._bonds_cache = None
        self._details_cache = None
    
    def clear_metadata_cache(self) -> None:
        """Очищает кэш метаданных (колонки) для принудительной перезагрузки.

        Сбрасывает кэш маппинга колонок. Описания полей хранятся в БД (describe_fields).
        """
        logger = get_data_update_logger()
        logger.info("[CLEAR METADATA CACHE] Clearing metadata cache (columns)")
        self._columns_cache = None
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
        """Загружает рейтинги из БД (bond_ratings) и возвращает словарь secid -> all_ratings.

        Использует BondRatingsRepository.get_all_latest_ratings_map(): один запрос с JOIN
        по bond_ratings, bonds и rating_agency. Структура совместима с логикой подмешивания
        рейтингов и выбора наихудшего рейтинга (_get_worst_rating).

        Returns:
            Словарь: ключ — SECID облигации, значение — словарь с ключом "all_ratings"
            (список рейтингов с agency_name_short_ru, rating_level_name_short_ru и др.).
        """
        return self._bond_ratings_repo.get_all_latest_ratings_map()
    
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

        logger = get_data_update_logger()
        logger.debug("[DATA LOADER] Added ratings to %s bonds", ratings_added)
    
    def _load_bondtype_map(self) -> Dict[str, Optional[str]]:
        """Загружает типы облигаций из БД (таблица emitents) и возвращает как словарь.

        Использует EmitentsRepository.get_secid_to_bondtype_map() для получения
        маппинга SECID -> type из таблиц bonds и emitents.

        Returns:
            Словарь, где ключ - SECID облигации, значение - тип облигации (строка).
            Пустой словарь при ошибке или отсутствии данных в БД.
        """
        try:
            emitents_repo = EmitentsRepository()
            bondtype_map = emitents_repo.get_secid_to_bondtype_map()
            logger = get_data_update_logger()
            logger.debug("Loaded bond types for %s bonds from DB", len(bondtype_map))
            return dict(bondtype_map)
        except Exception as exc:
            logger = get_data_update_logger()
            logger.warning(
                "Failed to load bond types from DB: %s - %s",
                type(exc).__name__,
                exc,
            )
            return {}
    
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

        logger = get_data_update_logger()
        logger.debug("[DATA LOADER] Added bond types to %s bonds", bondtypes_added)
    
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
