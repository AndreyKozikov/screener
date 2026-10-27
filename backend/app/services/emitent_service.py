"""Сервис чтения и подготовки данных эмитентов из репозитория базы данных."""

from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.logger import get_data_update_logger

logger = get_data_update_logger()


class EmitentService:
    """Сервис чтения данных эмитентов, уже сохранённых в базе данных.

    Attributes:
        data_dir (Path): Путь к директории с конфигурационными файлами.
        _emitents_repository (Optional[EmitentsRepository]): Репозиторий для работы с БД.
    """

    def __init__(
        self,
        data_dir: Path,
        emitents_repository: Optional[Any] = None,
    ):
        """Инициализирует экземпляр сервиса эмитентов.

        Args:
            data_dir (Path): Путь к директории с конфигурационными файлами.
            emitents_repository (Optional[Any]): Репозиторий для взаимодействия с БД.
        """
        self.data_dir = data_dir
        self._emitents_repository = emitents_repository

    def get_secid_to_emitent_title_index(self) -> Dict[str, str]:
        """Строит карту соответствия SECID и названия эмитента.

        Используется для быстрого поиска названия организации при фильтрации в скринере.

        Returns:
            Dict[str, str]: Словарь {SECID: Название_эмитента}.
        """
        if self._emitents_repository is None:
            logger.warning("EmitentsRepository не инициализирован, возвращаю пустой индекс")
            return {}
        return self._emitents_repository.get_secid_to_emitent_title_index()

    def get_emitent_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Извлекает данные эмитента для конкретной бумаги из базы данных.

        Args:
            secid (str): Идентификатор облигации.

        Returns:
            Optional[Dict[str, Any]]: Словарь с данными эмитента или None.
        """
        if self._emitents_repository is None:
            return None
        return self._emitents_repository.get_emitent_data_by_secid(secid)

    def extract_required_fields(self, emitent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Оставляет в записи эмитента поля, используемые API приложения.

        Args:
            emitent_data (Dict[str, Any]): Запись эмитента из репозитория.

        Returns:
            Dict[str, Any]: Словарь с ключевыми характеристиками эмитента.
        """
        return {
            "is_traded": emitent_data.get("is_traded"),
            "emitent_title": emitent_data.get("emitent_title"),
            "emitent_inn": emitent_data.get("emitent_inn"),
            "type": emitent_data.get("type"),
            "cci_rating_companies": emitent_data.get("cci_rating_companies"),
        }

# Singleton instance
_emitent_service: Optional[EmitentService] = None


def init_emitent_service(
    data_dir: Path,
    emitents_repository: Optional[Any] = None,
) -> None:
    """Инициализирует глобальный синглтон сервиса эмитентов.

    Args:
        data_dir (Path): Путь к директории данных.
        emitents_repository (Optional[Any]): Репозиторий эмитентов.
    """
    global _emitent_service
    _emitent_service = EmitentService(data_dir=data_dir, emitents_repository=emitents_repository)


def get_emitent_service() -> EmitentService:
    """Возвращает инициализированный экземпляр сервиса эмитентов.

    Returns:
        EmitentService: Глобальный сервис.

    Raises:
        RuntimeError: Если сервис не был проинициализирован.
    """
    if _emitent_service is None:
        raise RuntimeError("Emitent service not initialized")
    return _emitent_service
