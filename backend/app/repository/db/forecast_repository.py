"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import ForecastRepository as ForecastRepository

__all__ = ["ForecastRepository"]
