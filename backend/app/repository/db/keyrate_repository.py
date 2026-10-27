"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import KeyrateRepository as KeyrateRepository

__all__ = ["KeyrateRepository"]
