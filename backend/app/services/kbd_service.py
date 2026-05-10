"""Сервис управления данными кривой бескупонной доходности (КБД).

Модуль обеспечивает преобразование сырых рыночных данных КБД из базы данных
в структурированные объекты для визуализации на фронтенде, включая маппинг
параметров на русский язык и фильтрацию торговых дней.
"""

from typing import Dict, List, Optional, Any
import logging

from pathlib import Path

from app.repository.db.db_kbd import KbdRepository
from app.models import KbdDTO


class KbdService:
    """Сервисный слой для обработки данных КБД.

    Класс инкапсулирует логику подготовки данных КБД к отображению:
    очистку от неторговых дней, форматирование дат и перевод технических
    наименований столбцов на понятные пользователю заголовки.

    Attributes:
        _repo (KbdRepository): Репозиторий для доступа к таблице КБД.
        logger (Logger): Объект для ведения журналов событий.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Инициализирует сервис для работы с кривой бескупонной доходности.
        
        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется путь из config.paths.DB_PATH.
        """
        from config.paths import DB_PATH
        path = Path(db_path) if db_path is not None else DB_PATH
        self._repo = KbdRepository(db_path=path)
        self.logger = logging.getLogger(__name__)
        
        # Маппинг колонок БД (только те, что отдаём на фронт) на русские заголовки
        self._column_to_frontend: Dict[str, str] = {
            "date": "Дата",
            "time": "Время",
            "term_0_25": "Срок 0.25 лет",
            "term_0_5": "Срок 0.5 лет",
            "term_0_75": "Срок 0.75 лет",
            "term_1_0": "Срок 1.0 лет",
            "term_2_0": "Срок 2.0 лет",
            "term_3_0": "Срок 3.0 лет",
            "term_5_0": "Срок 5.0 лет",
            "term_7_0": "Срок 7.0 лет",
            "term_10_0": "Срок 10.0 лет",
            "term_15_0": "Срок 15.0 лет",
            "term_20_0": "Срок 20.0 лет",
        }

    def _raw_record_to_dto(self, record: Dict[str, Any]) -> Optional[KbdDTO]:
        """Преобразует одну сырую запись БД в KbdDTO. Пропускает выходные дни."""
        from datetime import datetime

        date_val = record.get("date")
        if not date_val:
            return None
        try:
            dt = datetime.strptime(date_val, "%Y-%m-%d")
            if dt.weekday() >= 5:  # суббота, воскресенье
                return None
        except (ValueError, TypeError):
            return None

        formatted: Dict[str, Any] = {}
        for eng, rus in self._column_to_frontend.items():
            value = record.get(eng)
            if eng == "date" and value:
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
                except (ValueError, TypeError):
                    pass
            formatted[rus] = value

        return KbdDTO.model_validate(formatted)

    def get_kbd_data_formatted(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[KbdDTO]:
        """Загружает из БД только колонки для фронта, фильтрует выходные, возвращает список KbdDTO."""
        raw_data = self._repo.get_kbd_data(
            date_from=date_from, date_to=date_to, for_frontend=True
        )
        result: List[KbdDTO] = []
        for record in raw_data:
            dto = self._raw_record_to_dto(record)
            if dto is not None:
                result.append(dto)
        return result


# Singleton instance
_kbd_service: Optional[KbdService] = None


def init_kbd_service(db_path: Optional[str] = None) -> None:
    """Инициализирует singleton экземпляр сервиса кривой бескупонной доходности.
    
    Создает глобальный экземпляр KbdService с указанным путем к базе данных.
    Должен быть вызван перед использованием get_kbd_service().
    
    Args:
        db_path: Опциональный путь к файлу базы данных SQLite.
            Если не указан, используется путь по умолчанию.
    """
    global _kbd_service
    _kbd_service = KbdService(db_path=db_path)


def get_kbd_service() -> Optional[KbdService]:
    """Получает singleton экземпляр сервиса кривой бескупонной доходности.
    
    Returns:
        Экземпляр KbdService для работы с данными кривой бескупонной доходности
        или None, если сервис не был инициализирован через init_kbd_service().
    """
    return _kbd_service
