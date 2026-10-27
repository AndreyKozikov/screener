import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from app.repository.db.event_detail_repository import EventDetailRepository
from app.repository.db.remote_repository import AttrDict
from config.paths import EMITENT_EVENTS_JSON_DIR

_repository = EventDetailRepository()

def get_event_text(emitent_inn: str, pseudo_guid: str, event_date: str) -> Optional[str]:
    """
    Извлекает текст события из JSON-файла.
    Ищет в файле {emitent_inn}.json, извлекает год из event_date.
    """
    json_path = EMITENT_EVENTS_JSON_DIR / f"{emitent_inn}.json"
    if not json_path.exists():
        return None
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Преобразуем в строку YYYY-MM-DD для сравнения и извлечения года
        date_str = str(event_date)
        year = date_str.split("-")[0]
        
        events_list = data.get(year, [])
        for event in events_list:
            if event.get("pseudoGUID") == pseudo_guid and event.get("event_date") == date_str:
                return event.get("full_text")
                
    except (json.JSONDecodeError, IOError, IndexError):
        pass
        
    return None

def save_event_changes(pseudo_guid: str, event_date: str, event_type: str, message_type: str, security_type: str) -> bool:
    """
    Обновляет event_type, message_type и security_type в БД и устанавливает is_edit = 1.
    Поиск по составному ключу pseudo_guid + event_date.
    """
    return _repository.save_event_changes(
        pseudo_guid, event_date, event_type, message_type, security_type
    )

def get_event_by_id(event_id: int) -> Optional[AttrDict]:
    """Возвращает событие по его ID."""
    return _repository.get_event_by_id(event_id)

def get_navigation_ids(current_id: int) -> Dict[str, Optional[int]]:
    """Возвращает ID предыдущего и следующего события."""
    return _repository.get_navigation_ids(current_id)

def get_first_unedited_id() -> Optional[int]:
    """Возвращает ID первого неотредактированного события."""
    return _repository.get_first_unedited_id()

def get_existing_types() -> Dict[str, List[str]]:
    """Возвращает уникальные значения event_type и message_type из всех записей базы данных."""
    return _repository.get_existing_types()

def get_stats() -> Dict[str, int]:
    """Возвращает количество отредактированных и общее количество событий."""
    return _repository.get_stats()

def delete_event(event_id: int) -> bool:
    """Удаляет событие из базы данных по его ID."""
    return _repository.delete_event(event_id)

if __name__ == "__main__":
    # Пример использования или тестовый запуск
    print("Events Loader Utility Loaded")
