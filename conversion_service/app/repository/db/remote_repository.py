"""HTTP repository client for the database service."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel

from conversion_service.config.settings import settings


class RemoteRepositoryError(RuntimeError):
    """The database service rejected a repository operation."""


class RepositoryConflictError(RemoteRepositoryError):
    """A repository write conflicted with a database constraint."""


class AttrDict(dict):
    """Dictionary with attribute access for repository rows."""

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
    _shared_client = httpx.Client(timeout=300.0)

    def __init__(self) -> None:
        self._base_url = settings.DB_REPOSITORY_URL.rstrip("/")
        self._api_key = settings.DB_REPOSITORY_API_KEY.get_secret_value()

    def _invoke(self, method: str, *args: Any, **kwargs: Any) -> Any:
        headers = {"X-API-Key": self._api_key} if self._api_key else {}
        response = self._shared_client.post(
            f"{self._base_url}/internal/repository/call",
            json={
                "repository": self.repository,
                "method": method,
                "args": _encode(list(args)),
                "kwargs": _encode(kwargs),
            },
            headers=headers,
        )
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


class BondRatingsRepository(RemoteRepository):
    repository = "bond_ratings"


class BondFloatParamsRepository(RemoteRepository):
    repository = "bond_float_params"


class CurrencyrateRepository(RemoteRepository):
    repository = "currency_rates"


class DBCoupon(RemoteRepository):
    repository = "coupons"


class KbdRepository(RemoteRepository):
    repository = "kbd"


class EmitentEdisclosureRepository(RemoteRepository):
    repository = "emitent_edisclosure"


class EmitentsRepository(RemoteRepository):
    repository = "emitents"


class EmissionDocumentRepository(RemoteRepository):
    repository = "emission_documents"

    def get_all_documents_by_metadata(self) -> dict[tuple[str, str], list[str]]:
        rows = self._invoke("get_all_documents_by_metadata")
        return {
            (str(r[0]).strip(), str(r[1]).strip()): [str(u).strip() for u in r[2]]
            for r in rows
            if len(r) >= 3 and r[0] and r[1]
        }



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
    "BondFloatParamsRepository",
    "BondRatingsRepository",
    "BondsRepository",
    "CurrencyrateRepository",
    "DBCoupon",
    "EmitentEdisclosureRepository",
    "EmitentsRepository",
    "EmissionDocumentRepository",
    "EventDetailRepository",
    "ForecastRepository",
    "KbdRepository",
    "PortfolioImportRepository",
    "KeyrateRepository",
    "RemoteRepository",
    "RemoteRepositoryError",
    "RepositoryConflictError",
    "RuoniaRepository",
    "TradingHistoryRepository",
    "UsersRepository",
]
