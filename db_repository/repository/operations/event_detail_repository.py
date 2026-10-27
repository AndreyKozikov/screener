from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from sqlmodel import Session, create_engine, func, select
from db_repository.models.orm.event_detail import EventDetail


class EventDetailRepository:
    """Репозиторий для работы с сущностью EventDetail в SQLite."""

    def __init__(self, db_path: Optional[Path]):

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

    def get_existing_types(self) -> Dict[str, list[str]]:
        """Return sorted event and message type choices for the standalone editor."""
        with Session(self._engine) as session:
            results = session.exec(
                select(EventDetail.message_type, EventDetail.event_type).where(EventDetail.is_edit == 1)
            ).all()

        message_types = sorted({row.message_type.strip() for row in results if row.message_type and row.message_type.strip()})
        event_types = sorted({row.event_type.strip() for row in results if row.event_type and row.event_type.strip()})
        return {"event_types": event_types, "message_types": message_types}

    def get_event_by_id(self, event_id: int) -> Optional[EventDetail]:
        """Return an event by its primary key for the standalone editor."""
        with Session(self._engine) as session:
            return session.get(EventDetail, event_id)

    def save_event_changes(
        self,
        pseudo_guid: str,
        event_date: str,
        event_type: str,
        message_type: str,
        security_type: str,
    ) -> bool:
        """Update editor-controlled fields and mark matching rows as reviewed."""
        with Session(self._engine) as session:
            rows = session.exec(
                select(EventDetail).where(
                    EventDetail.pseudo_guid == pseudo_guid,
                    EventDetail.event_date == event_date,
                )
            ).all()
            if not rows:
                return False
            for event in rows:
                event.event_type = event_type
                event.message_type = message_type
                event.security_type = security_type
                event.is_edit = 1
                session.add(event)
            session.commit()
            return True

    def get_navigation_ids(self, current_id: int) -> Dict[str, Optional[int]]:
        """Return adjacent event ids for editor navigation."""
        with Session(self._engine) as session:
            previous = session.exec(
                select(EventDetail.id)
                .where(EventDetail.id < current_id)
                .order_by(EventDetail.id.desc())
                .limit(1)
            ).first()
            following = session.exec(
                select(EventDetail.id)
                .where(EventDetail.id > current_id)
                .order_by(EventDetail.id.asc())
                .limit(1)
            ).first()
            return {"prev": previous, "next": following}

    def get_first_unedited_id(self) -> Optional[int]:
        """Return the first event which has not yet been reviewed."""
        with Session(self._engine) as session:
            return session.exec(
                select(EventDetail.id)
                .where(EventDetail.is_edit == 0)
                .order_by(EventDetail.id.asc())
                .limit(1)
            ).first()

    def get_stats(self) -> Dict[str, int]:
        """Return edited and total event counts for the editor progress bar."""
        with Session(self._engine) as session:
            total = session.exec(select(func.count(EventDetail.id))).one()
            edited = session.exec(
                select(func.count(EventDetail.id)).where(EventDetail.is_edit == 1)
            ).one()
            return {"edited": edited, "total": total}

    def delete_event(self, event_id: int) -> bool:
        """Delete one event by primary key."""
        with Session(self._engine) as session:
            event = session.get(EventDetail, event_id)
            if event is None:
                return False
            session.delete(event)
            session.commit()
            return True

    def get_by_guid_and_date(self, pseudo_guid: str, event_date: str) -> Optional[EventDetail]:
        """Возвращает детали события по pseudo_guid и event_date."""
        with Session(self._engine) as session:
            return session.query(EventDetail).filter(
                EventDetail.pseudo_guid == pseudo_guid,
                EventDetail.event_date == event_date
            ).first()

events_detail_repository: Optional[EventDetailRepository] = None

