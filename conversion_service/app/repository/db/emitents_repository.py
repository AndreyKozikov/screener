"""Compatibility import for the database microservice client."""

from conversion_service.app.repository.db.remote_repository import (
    EmitentsRepository as EmitentsRepository,
)

__all__ = ["EmitentsRepository"]
