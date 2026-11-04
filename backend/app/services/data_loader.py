"""Загружает локальный маппинг заголовков колонок и кэширует его в памяти."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.repository.files.file_storage import FileStorage


class DataLoader:
    """Кэш маппинга русских заголовков из локального ``columns.json``."""

    def __init__(
        self,
        data_dir: Path,
        file_storage: Optional[FileStorage] = None,
    ):
        """Инициализирует загрузчик локальной конфигурации."""
        self.data_dir = Path(data_dir)
        self._file_storage = file_storage if file_storage is not None else FileStorage()
        self._columns_cache: Optional[Dict[str, str]] = None

    async def get_bonds(self) -> List[Any]:
        """Оставляет совместимость с read-only фильтрами без локального списка облигаций."""
        return []

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
