"""HTTP client for the database microservice."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel

from app.repository.db.client import get_db_repository_client


class RemoteRepositoryError(RuntimeError):
    """Database service returned an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code


class RepositoryAuthError(RemoteRepositoryError):
    """The database service rejected the API key."""


class RepositoryConflictError(RemoteRepositoryError):
    """A repository write conflicted with a unique constraint."""


class RepositoryUnavailableError(RemoteRepositoryError):
    """The database service could not be reached."""

    def __init__(self, detail: str) -> None:
        super().__init__(0, detail)


class AttrDict(dict):
    """Dictionary that preserves the attribute-style access of former ORM rows."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _encode(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _encode(value.model_dump(mode="python"))
    if isinstance(value, datetime):
        return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"$type": "time", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"$type": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"$type": "uuid", "value": str(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return {"$type": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, set):
        return {"$type": "set", "items": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, (list, frozenset)):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        kind = value.get("$type")
        if kind == "date":
            return date.fromisoformat(value["value"])
        if kind == "datetime":
            return datetime.fromisoformat(value["value"])
        if kind == "time":
            return time.fromisoformat(value["value"])
        if kind == "decimal":
            return Decimal(value["value"])
        if kind == "uuid":
            return UUID(value["value"])
        if kind == "tuple":
            return tuple(_decode(item) for item in value["items"])
        if kind == "set":
            return set(_decode(item) for item in value["items"])
        return AttrDict({key: _decode(item) for key, item in value.items()})
    return value


class RemoteRepository:
    """Transparent synchronous proxy to one allow-listed repository."""

    repository: str

    def __init__(self) -> None:
        """Configure the client; database paths remain owned by the service."""
        self._client = get_db_repository_client()

    def _invoke(self, method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            response = self._client.post(
                "/internal/repository/call",
                json={
                    "repository": self.repository,
                    "method": method,
                    "args": _encode(list(args)),
                    "kwargs": _encode(kwargs),
                },
            )
        except httpx.TransportError as exc:
            raise RepositoryUnavailableError(str(exc)) from exc

        if response.status_code in (401, 403):
            raise RepositoryAuthError(response.status_code, _error_detail(response))
        if response.status_code == 409:
            raise RepositoryConflictError(409, _error_detail(response))
        if response.is_error:
            raise RemoteRepositoryError(response.status_code, _error_detail(response))
        return _decode(response.json()["result"])

    def __getattr__(self, method: str):
        if method.startswith("_"):
            raise AttributeError(method)

        def invoke(*args: Any, **kwargs: Any) -> Any:
            return self._invoke(method, *args, **kwargs)

        return invoke


class BlogRepository(RemoteRepository):
    repository = "blog"


class BondFloatParamsRepository(RemoteRepository):
    repository = "bond_float_params"


class BondRatingsRepository(RemoteRepository):
    repository = "bond_ratings"


class BondsRepository(RemoteRepository):
    repository = "bonds"

    def get_all_bonds_metadata(
        self, rating: str | None = None
    ) -> dict[str, tuple[str, str]]:
        result = self._invoke("get_all_bonds_metadata", rating=rating)
        return {
            str(k).strip(): (str(v[0]).strip(), str(v[1]).strip())
            for k, v in result.items()
            if len(v) >= 2
        }


class CurrencyrateRepository(RemoteRepository):
    repository = "currency_rates"


class DBCoupon(RemoteRepository):
    repository = "coupons"


class KbdRepository(RemoteRepository):
    repository = "kbd"


class DescribeRepository(RemoteRepository):
    repository = "descriptions"


class EmissionDocumentRepository(RemoteRepository):
    repository = "emission_documents"

    def get_all_documents_by_metadata(self) -> dict[tuple[str, str], list[str]]:
        rows = self._invoke("get_all_documents_by_metadata")
        return {
            (str(r[0]).strip(), str(r[1]).strip()): [str(u).strip() for u in r[2]]
            for r in rows
            if len(r) >= 3 and r[0] and r[1]
        }



class EmitentEdisclosureRepository(RemoteRepository):
    repository = "emitent_edisclosure"


class EmitentsRepository(RemoteRepository):
    repository = "emitents"


class EventDetailRepository(RemoteRepository):
    repository = "events"


class ForecastRepository(RemoteRepository):
    repository = "forecasts"


class KeyrateRepository(RemoteRepository):
    repository = "keyrates"


class RuoniaRepository(RemoteRepository):
    repository = "ruonia"


class UsersRepository(RemoteRepository):
    repository = "users"


class PortfolioImportRepository(RemoteRepository):
    repository = "portfolios"


class TradingHistoryRepository(RemoteRepository):
    repository = "trading_history"


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        return str(body.get("detail", body)) if isinstance(body, dict) else str(body)
    except ValueError:
        return response.text or f"Database service returned HTTP {response.status_code}"


__all__ = [
    "AttrDict",
    "BlogRepository",
    "BondFloatParamsRepository",
    "BondRatingsRepository",
    "BondsRepository",
    "CurrencyrateRepository",
    "DBCoupon",
    "DescribeRepository",
    "EmissionDocumentRepository",
    "EmitentEdisclosureRepository",
    "EmitentsRepository",
    "EventDetailRepository",
    "ForecastRepository",
    "KbdRepository",
    "KeyrateRepository",
    "PortfolioImportRepository",
    "RemoteRepository",
    "RemoteRepositoryError",
    "RepositoryAuthError",
    "RepositoryConflictError",
    "RepositoryUnavailableError",
    "RuoniaRepository",
    "TradingHistoryRepository",
]
