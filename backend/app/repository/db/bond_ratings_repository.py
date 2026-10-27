"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import BondRatingsRepository as BondRatingsRepository

__all__ = ["BondRatingsRepository"]
