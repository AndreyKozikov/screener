from pathlib import Path
from typing import Optional, Set, Tuple

from sqlmodel import Session, create_engine

from config.paths import DB_PATH
from app.models.entities.event_detail import EventDetail


class EventDetailRepository:
    """Репозиторий для работы с сущностью EventDetail в SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    def save(self, event: EventDetail) -> EventDetail:
        """Сохраняет детали события в базу данных."""
        with Session(self._engine) as session:
            session.add(event)
            session.commit()
            session.refresh(event)
        return event

    def get_processed_events_keys(self) -> Set[Tuple[str, str]]:
        """Возвращает множество пар (pseudo_guid, event_date) всех сохраненных событий."""
        with Session(self._engine) as session:
            results = session.query(EventDetail.pseudo_guid, EventDetail.event_date).all()
        return {(res.pseudo_guid, str(res.event_date)) for res in results}

    def get_existing_types(self) -> Tuple[Set[str], Set[str]]:
        """Возвращает уникальные значения message_type и event_type у записей с is_edit=1."""
        with Session(self._engine) as session:
            results = session.query(EventDetail.message_type, EventDetail.event_type).filter(EventDetail.is_edit == 1).all()
        
        message_types = {res.message_type for res in results if res.message_type}
        event_types = {res.event_type for res in results if res.event_type}
        return message_types, event_types

    def get_by_guid_and_date(self, pseudo_guid: str, event_date: str) -> Optional[EventDetail]:
        """Возвращает детали события по pseudo_guid и event_date."""
        with Session(self._engine) as session:
            return session.query(EventDetail).filter(
                EventDetail.pseudo_guid == pseudo_guid,
                EventDetail.event_date == event_date
            ).first()
