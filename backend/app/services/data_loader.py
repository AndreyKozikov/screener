"""Модуль для загрузки и кэширования данных об облигациях.

Обеспечивает эффективную работу со списками бумаг, детальной информацией и маппингом колонок.
Интегрирует данные из MOEX API с локальными рейтингами и информацией об эмитентах из БД.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models import BondListItem
from app.repository.files.file_storage import FileStorage

from app.utils.rating_utils import get_rating_index, standardize_rating
from app.services.moex_client import MoexClient
from app.utils.logger import get_data_update_logger


class DataLoader:
    """Загрузчик и менеджер кэша данных облигаций.

    Отвечает за получение данных из MOEX, их предварительную обработку, обогащение
    информацией из базы данных (рейтинги, типы) и предоставление кэшированного доступа
    другим частям приложения.

    Attributes:
        data_dir (Path): Путь к директории с локальными файлами данных.
        _moex_client (MoexClient): Клиент для взаимодействия с API MOEX.
        _file_storage (FileStorage): Компонент для работы с файловой системой.
        _bonds_cache (Optional[List[BondListItem]]): Кэш основного списка облигаций.
        _details_cache (Optional[Dict[str, Dict]]): Кэш детальной информации.
        _columns_cache (Optional[Dict[str, str]]): Кэш маппинга имен колонок.
    """

    def __init__(
        self,
        data_dir: Path,
        moex_client: Optional[MoexClient] = None,
        file_storage: Optional[FileStorage] = None,
    ):
        """Инициализирует экземпляр DataLoader.

        Args:
            data_dir (Path): Путь к директории с локальными файлами конфигурации (columns.json).
            moex_client (Optional[MoexClient]): Клиент для работы с API MOEX.
            file_storage (Optional[FileStorage]): Компонент для работы с файловой системой.
        """
        self.data_dir = Path(data_dir)
        self._moex_client = moex_client if moex_client is not None else MoexClient()
        self._file_storage = file_storage if file_storage is not None else FileStorage()
        self._bonds_cache: Optional[List[BondListItem]] = None
        self._details_cache: Optional[Dict[str, Dict]] = None
        self._columns_cache: Optional[Dict[str, str]] = None

    async def get_bonds(self) -> List[BondListItem]:
        """Возвращает текущий кэшированный список облигаций для скринера.

        Returns:
            List[BondListItem]: Список объектов облигаций или пустой список, если кэш пуст.
        """
        if self._bonds_cache is None:
            return []
        return self._bonds_cache

    async def get_column_mapping(self) -> Dict[str, str]:
        """Обеспечивает доступ к маппингу системных имен полей в читаемые заголовки.

        Returns:
            Dict[str, str]: Словарь {поле: заголовок}.
        """
        if self._columns_cache is None:
            self._columns_cache = self._load_column_mapping()
        return self._columns_cache

    
    def _load_column_mapping(self) -> Dict[str, str]:
        """Загружает описания колонок из локального файла columns.json.

        Returns:
            Dict[str, str]: Словарь соответствий технических имен и заголовков.
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
        """Очищает кэшированные данные облигаций. Полезно при обновлении БД."""
        self._bonds_cache = None
        self._details_cache = None
    
    def clear_metadata_cache(self) -> None:
        """Очищает кэш маппинга колонок."""
        logger = get_data_update_logger()
        logger.info("[CLEAR METADATA CACHE] Clearing metadata cache (columns)")
        self._columns_cache = None
        logger.info("[CLEAR METADATA CACHE] Metadata cache cleared successfully")

    
    def _get_worst_rating(self, ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Выбирает наиболее консервативный (худший) рейтинг из предоставленного списка.

        Игнорирует статус "Отозван", если доступны другие активные рейтинги.

        Args:
            ratings_list (List[Dict[str, Any]]): Список доступных рейтингов для бумаги.

        Returns:
            Optional[Dict[str, Any]]: Объект худшего рейтинга или None.
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
            
            rating_index = get_rating_index(standardize_rating(rating_level))
            if rating_index is not None and rating_index > worst_index:
                worst_index = rating_index
                worst_rating = rating
        
        return worst_rating

# Singleton instance
_data_loader: Optional[DataLoader] = None


def init_data_loader(data_dir: Path) -> None:
    """Инициализирует глобальный экземпляр DataLoader.

    Должен быть вызван при старте приложения до любых обращений к get_data_loader().

    Args:
        data_dir (Path): Директория с ресурсами данных.
    """
    global _data_loader
    _data_loader = DataLoader(
        data_dir,
        moex_client=MoexClient(),
        file_storage=FileStorage(),
    )


def get_data_loader() -> DataLoader:
    """Возвращает инициализированный экземпляр DataLoader.

    Returns:
        DataLoader: Глобальный загрузчик данных.

    Raises:
        RuntimeError: Если загрузчик еще не был инициализирован через init_data_loader.
    """
    if _data_loader is None:
        raise RuntimeError("Data loader not initialized")
    return _data_loader
