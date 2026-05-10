import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlmodel import Session, create_engine, select, func
from app.models.entities.event_detail import EventDetail
from config.paths import DB_PATH, EMITENT_EVENTS_JSON_DIR

# Настройка движка БД
engine = create_engine(
    f"sqlite:///{DB_PATH.resolve()}",
    connect_args={"check_same_thread": False},
    echo=False,
)

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
    with Session(engine) as session:
        statement = select(EventDetail).where(
            EventDetail.pseudo_guid == pseudo_guid,
            EventDetail.event_date == event_date
        )
        results = session.exec(statement).all()
        
        if not results:
            return False
        
        for event in results:
            event.event_type = event_type
            event.message_type = message_type
            event.security_type = security_type
            event.is_edit = 1
            session.add(event)
        
        session.commit()
        return True

def get_event_by_id(event_id: int) -> Optional[EventDetail]:
    """Возвращает событие по его ID."""
    with Session(engine) as session:
        return session.get(EventDetail, event_id)

def get_navigation_ids(current_id: int) -> Dict[str, Optional[int]]:
    """Возвращает ID предыдущего и следующего события."""
    with Session(engine) as session:
        # Находим ID меньше текущего (максимальный из них)
        prev_id = session.exec(
            select(EventDetail.id)
            .where(EventDetail.id < current_id)
            .order_by(EventDetail.id.desc())
            .limit(1)
        ).first()
        
        # Находим ID больше текущего (минимальный из них)
        next_id = session.exec(
            select(EventDetail.id)
            .where(EventDetail.id > current_id)
            .order_by(EventDetail.id.asc())
            .limit(1)
        ).first()
        
        return {"prev": prev_id, "next": next_id}

def get_first_unedited_id() -> Optional[int]:
    """Возвращает ID первого неотредактированного события."""
    with Session(engine) as session:
        return session.exec(
            select(EventDetail.id)
            .where(EventDetail.is_edit == 0)
            .order_by(EventDetail.id.asc())
            .limit(1)
        ).first()

def get_existing_types() -> Dict[str, List[str]]:
    """Возвращает уникальные значения event_type и message_type из отредактированных записей."""
    with Session(engine) as session:
        event_types = session.exec(
            select(EventDetail.event_type)
            .where(EventDetail.is_edit == 1, EventDetail.event_type != None)
        ).all()
        message_types = session.exec(
            select(EventDetail.message_type)
            .where(EventDetail.is_edit == 1, EventDetail.message_type != None)
        ).all()
        
        return {
            "event_types": sorted(list(set(event_types))),
            "message_types": sorted(list(set(message_types)))
        }

def get_stats() -> Dict[str, int]:
    """Возвращает количество отредактированных и общее количество событий."""
    with Session(engine) as session:
        total = session.exec(select(func.count(EventDetail.id))).one()
        edited = session.exec(select(func.count(EventDetail.id)).where(EventDetail.is_edit == 1)).one()
        return {"edited": edited, "total": total}

def delete_event(event_id: int) -> bool:
    """Удаляет событие из базы данных по его ID."""
    with Session(engine) as session:
        event = session.get(EventDetail, event_id)
        if event:
            session.delete(event)
            session.commit()
            return True
        return False

if __name__ == "__main__":
    # Пример использования или тестовый запуск
    print("Events Loader Utility Loaded")
