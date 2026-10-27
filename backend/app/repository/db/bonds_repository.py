"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import BondsRepository as BondsRepository

__all__ = ["BondsRepository"]
