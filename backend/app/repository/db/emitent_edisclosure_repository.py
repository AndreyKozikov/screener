"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import EmitentEdisclosureRepository as EmitentEdisclosureRepository

__all__ = ["EmitentEdisclosureRepository"]
