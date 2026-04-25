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
