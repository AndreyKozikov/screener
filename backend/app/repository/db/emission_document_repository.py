"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import EmissionDocumentRepository as EmissionDocumentRepository

__all__ = ["EmissionDocumentRepository"]
