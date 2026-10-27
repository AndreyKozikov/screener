"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import KbdRepository as KbdRepository

__all__ = ["KbdRepository"]
