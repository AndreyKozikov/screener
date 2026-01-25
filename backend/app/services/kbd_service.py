from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from app.services.db_refresher import DBkbd


class KbdService:
    """
    Сервисный слой для работы с данными кривой бескупонной доходности (KBD).
    
    Преобразует сырые данные из БД в формат, ожидаемый фронтендом,
    применяя обратный маппинг столбцов на русские наименования.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Инициализация сервиса
        
        Args:
            db_path: Путь к файлу базы данных. Если не указан, используется backend/db/bonds.db
        """
        self.db_kbd = DBkbd(db_path=db_path)
        self.logger = logging.getLogger(__name__)
        
        # Обратный маппинг английских столбцов на русские заголовки
        self.reverse_column_mapping = {
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
    
    def format_kbd_response(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Преобразует сырые данные из БД в формат, ожидаемый фронтендом.
        
        Применяет обратный маппинг столбцов на русские наименования.
        
        Args:
            raw_data: Список словарей с сырыми данными из БД (ключи - английские названия столбцов)
        
        Returns:
            Список словарей с данными для фронтенда (ключи - русские названия столбцов)
        """
        formatted_data = []
        
        for record in raw_data:
            formatted_record = {}
            
            for english_col, russian_col in self.reverse_column_mapping.items():
                value = record.get(english_col)
                # Сохраняем значение как есть (может быть None, float, str)
                formatted_record[russian_col] = value
            
            formatted_data.append(formatted_record)
        
        return formatted_data
    
    def get_kbd_data_formatted(self) -> List[Dict[str, Any]]:
        """
        Получает данные из БД и преобразует их в формат для фронтенда.
        
        Returns:
            Список словарей с данными для фронтенда (ключи - русские названия столбцов)
        """
        raw_data = self.db_kbd.get_kbd_data()
        return self.format_kbd_response(raw_data)


# Singleton instance
_kbd_service: Optional[KbdService] = None


def init_kbd_service(db_path: Optional[str] = None) -> None:
    """Инициализирует глобальный экземпляр KbdService"""
    global _kbd_service
    _kbd_service = KbdService(db_path=db_path)


def get_kbd_service() -> Optional[KbdService]:
    """Возвращает глобальный экземпляр KbdService"""
    return _kbd_service
