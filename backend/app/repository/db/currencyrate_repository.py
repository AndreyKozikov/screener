"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import CurrencyrateRepository as CurrencyrateRepository

__all__ = ["CurrencyrateRepository"]
