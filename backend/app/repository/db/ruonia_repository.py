"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import RuoniaRepository as RuoniaRepository

__all__ = ["RuoniaRepository"]
