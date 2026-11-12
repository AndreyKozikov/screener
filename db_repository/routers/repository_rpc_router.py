"""Internal HTTP boundary for backend database operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from db_repository.core.security import require_api_key
from db_repository.models.repository_rpc import RepositoryCall, RepositoryResult
from db_repository.services.repository_rpc_service import call_repository

repository_rpc_router = APIRouter(
    prefix="/internal/repository",
    tags=["internal"],
    dependencies=[Depends(require_api_key)],
)


@repository_rpc_router.post("/call", response_model=RepositoryResult)
def repository_call(payload: RepositoryCall) -> RepositoryResult:
    """Validate and dispatch an allow-listed repository operation."""
    try:
        return RepositoryResult(result=call_repository(payload))
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Database constraint conflict") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


__all__ = ["repository_rpc_router"]
