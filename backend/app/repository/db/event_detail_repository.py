"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import EventDetailRepository as EventDetailRepository

__all__ = ["EventDetailRepository"]

def get_events_detail_repository() -> EventDetailRepository:
    """Create the remote event repository; database paths belong to the service."""
    return EventDetailRepository()
