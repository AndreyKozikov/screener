"""Сервис для работы с данными кривой бескупонной доходности (KBD).

Этот модуль содержит класс KbdService для работы с данными кривой бескупонной
доходности. Преобразует сырые данные из базы данных в формат, ожидаемый фронтендом,
применяя обратный маппинг столбцов на русские наименования.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from app.repository.db.db_kbd import DBkbd


class KbdService:
    """Сервисный слой для работы с данными кривой бескупонной доходности (KBD).
    
    Класс обеспечивает преобразование сырых данных из базы данных в формат,
    ожидаемый фронтендом. Применяет обратный маппинг английских названий столбцов
    на русские наименования и преобразует форматы дат для удобства отображения.
    
    Attributes:
        db_kbd: Экземпляр DBkbd для работы с таблицей kbd в БД.
        logger: Логгер для записи событий и ошибок.
        reverse_column_mapping: Обратный маппинг английских столбцов на русские заголовки.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Инициализирует сервис для работы с кривой бескупонной доходности.
        
        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется путь по умолчанию: backend/db/bonds.db
        """
        self.db_kbd = DBkbd(db_path=db_path)
        self.logger = logging.getLogger(__name__)
        
        self.reverse_column_mapping: Dict[str, str] = {
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
            "term_30_0": "Срок 30.0 лет"
        }
        """Обратный маппинг английских столбцов на русские заголовки."""
    
    def format_kbd_response(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Преобразует сырые данные из БД в формат, ожидаемый фронтендом.
        
        Применяет обратный маппинг столбцов на русские наименования и преобразует
        форматы данных для удобства отображения на фронтенде. Преобразует дату из
        формата YYYY-MM-DD (формат БД) обратно в DD.MM.YYYY (формат фронтенда).
        
        Args:
            raw_data: Список словарей с сырыми данными из БД. Каждый словарь содержит
                данные одной записи с ключами - английскими названиями столбцов
                (date, time, term_0_25, и т.д.).
        
        Returns:
            Список словарей с данными для фронтенда. Каждый словарь содержит данные
            одной записи с ключами - русскими названиями столбцов (Дата, Время,
            Срок 0.25 лет, и т.д.). Даты преобразованы в формат DD.MM.YYYY.
        """
        from datetime import datetime
        
        formatted_data = []
        
        for record in raw_data:
            formatted_record = {}
            
            for english_col, russian_col in self.reverse_column_mapping.items():
                value = record.get(english_col)
                
                # Преобразуем дату из формата YYYY-MM-DD в DD.MM.YYYY
                if english_col == "date" and value:
                    try:
                        # Парсим дату из формата YYYY-MM-DD
                        date_obj = datetime.strptime(value, "%Y-%m-%d")
                        # Преобразуем в формат DD.MM.YYYY для фронтенда
                        value = date_obj.strftime("%d.%m.%Y")
                    except (ValueError, TypeError):
                        # Если не удалось преобразовать, оставляем как есть
                        pass
                
                # Сохраняем значение (может быть None, float, str)
                formatted_record[russian_col] = value
            
            formatted_data.append(formatted_record)
        
        return formatted_data
    
    def get_kbd_data_formatted(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получает данные из БД и преобразует их в формат для фронтенда.
        
        Загружает данные кривой бескупонной доходности из базы данных с опциональной
        фильтрацией по диапазону дат и преобразует их в формат, ожидаемый фронтендом
        (русские названия столбцов, формат даты DD.MM.YYYY).
        
        Args:
            date_from: Начальная дата диапазона в формате DD.MM.YYYY (включительно).
                Если None, фильтр не применяется (выбираются все записи до date_to).
            date_to: Конечная дата диапазона в формате DD.MM.YYYY (включительно).
                Если None, фильтр не применяется (выбираются все записи от date_from).
        
        Returns:
            Список словарей с данными для фронтенда. Каждый словарь содержит данные
            одной записи с ключами - русскими названиями столбцов. Результаты отсортированы
            по дате в порядке убывания (от новых к старым).
        """
        raw_data = self.db_kbd.get_kbd_data(date_from=date_from, date_to=date_to)
        return self.format_kbd_response(raw_data)


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
