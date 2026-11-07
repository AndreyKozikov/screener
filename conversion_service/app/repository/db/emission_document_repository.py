"""Compatibility import for the database microservice client."""

from conversion_service.app.repository.db.remote_repository import (
    EmissionDocumentRepository as EmissionDocumentRepository,
)

__all__ = ["EmissionDocumentRepository"]
