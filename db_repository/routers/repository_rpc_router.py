"""Internal HTTP boundary for backend database operations."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError

from db_repository.config.settings import settings
from db_repository.models.repository_rpc import RepositoryCall, RepositoryResult
from db_repository.services.repository_rpc_service import call_repository

repository_rpc_router = APIRouter(prefix="/internal/repository", tags=["internal"])


@repository_rpc_router.post("/call", response_model=RepositoryResult)
def repository_call(
    payload: RepositoryCall,
    api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> RepositoryResult:
    """Validate and dispatch an allow-listed repository operation."""
    expected_key = settings.api_key.get_secret_value()
    if expected_key and not secrets.compare_digest(api_key or "", expected_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    try:
        return RepositoryResult(result=call_repository(payload))
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Database constraint conflict") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


__all__ = ["repository_rpc_router"]
