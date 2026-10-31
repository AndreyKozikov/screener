"""Allow-listed RPC dispatcher for backend database operations."""

from __future__ import annotations

import inspect
import logging
from datetime import date, datetime, time
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, get_type_hints
from uuid import UUID

from pydantic import BaseModel, TypeAdapter
from pydantic_core import PydanticUndefined

from db_repository.config.paths import BLOG_DB_PATH, DATA_DIR, DB_PATH, HISTORY_DB_PATH
from db_repository.models.repository_rpc import RepositoryCall
from db_repository.repository.operations.blog_repository import BlogRepository
from db_repository.repository.operations.bond_float_params_repository import BondFloatParamsRepository
from db_repository.repository.operations.bond_ratings_repository import BondRatingsRepository
from db_repository.repository.operations.bonds_repository import BondsRepository
from db_repository.repository.operations.currencyrate_repository import CurrencyrateRepository
from db_repository.repository.operations.db_coupon import DBCoupon
from db_repository.repository.operations.db_kbd import KbdRepository
from db_repository.repository.operations.describe_repository import DescribeRepository
from db_repository.repository.operations.emission_document_repository import EmissionDocumentRepository
from db_repository.repository.operations.emitent_edisclosure_repository import EmitentEdisclosureRepository
from db_repository.repository.operations.emitents_repository import EmitentsRepository
from db_repository.repository.operations.event_detail_repository import EventDetailRepository
from db_repository.repository.operations.forecast_repository import ForecastRepository
from db_repository.repository.operations.keyrate_repository import KeyrateRepository
from db_repository.repository.operations.ruonia_repository import RuoniaRepository
from db_repository.repository.operations.trading_history_repository import TradingHistoryRepository

logger = logging.getLogger(__name__)


def _encode(value: Any) -> Any:
    """Encode Python/Pydantic values into a lossless JSON-compatible form."""
    if isinstance(value, BaseModel):
        return _encode(value.model_dump(mode="python"))
    if isinstance(value, BaseException):
        return str(value)
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
    if hasattr(value, "_mapping"):
        mapping = dict(value._mapping)
        # SQLAlchemy Row objects returned by ``select(Model)`` may expose a
        # single ORM instance under the model name (for example,
        # {"DBruonia": <DBruonia>}). Return that model as a normal field dict
        # so repository clients can read its attributes directly.
        if len(mapping) == 1:
            row_value = next(iter(mapping.values()))
            if isinstance(row_value, BaseModel):
                return _encode(row_value)
        return _encode(mapping)
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _encode(vars(value))
    return value


def _decode(value: Any) -> Any:
    """Restore tagged scalar/container values from the RPC wire format."""
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
        return {key: _decode(item) for key, item in value.items()}
    return value


def _repository_factories() -> dict[str, Any]:
    """Build repositories with database paths controlled by this service."""
    return {
        "blog": lambda: BlogRepository(db_path=BLOG_DB_PATH),
        "bond_float_params": lambda: BondFloatParamsRepository(db_path=DB_PATH),
        "bond_ratings": lambda: BondRatingsRepository(db_path=DB_PATH),
        "bonds": lambda: BondsRepository(db_path=DB_PATH),
        "currency_rates": lambda: CurrencyrateRepository(db_path=DB_PATH),
        "coupons": lambda: DBCoupon(db_path=str(DB_PATH)),
        "kbd": lambda: KbdRepository(db_path=DB_PATH),
        "descriptions": lambda: DescribeRepository(db_path=DB_PATH),
        "emission_documents": lambda: EmissionDocumentRepository(db_path=DB_PATH),
        "emitent_edisclosure": lambda: EmitentEdisclosureRepository(db_path=DB_PATH),
        "emitents": lambda: EmitentsRepository(db_path=DB_PATH),
        "events": lambda: EventDetailRepository(db_path=DB_PATH),
        "forecasts": lambda: ForecastRepository(db_path=DB_PATH),
        "keyrates": lambda: KeyrateRepository(db_path=DB_PATH),
        "ruonia": lambda: RuoniaRepository(db_path=DB_PATH),
        "trading_history": lambda: TradingHistoryRepository(db_path=HISTORY_DB_PATH),
    }


_FACTORIES = _repository_factories()

_ALLOWED_OPERATIONS: dict[str, frozenset[str]] = {
    "blog": frozenset({"create", "delete", "get_by_slug", "list_articles", "update"}),
    "bond_float_params": frozenset({"get_bond_ids_with_find", "get_by_bond_id", "get_existing_bond_ids", "upsert"}),
    "bond_ratings": frozenset({"get_agency_name_short_ru_by_agency_id", "get_ratings_by_secid", "upsert_ratings_for_bond"}),
    "bonds": frozenset({
        "get_all_secids", "get_bond_detail_by_secid", "get_bond_id_by_secid", "get_bonds_for_ratings_pipeline",
        "get_emitent_inn_by_secid", "get_floater_secids", "get_id_secid_list",
        "get_reg_number_by_secid", "get_secids_by_ids", "get_secids_by_regnumber",
    }),
    "currency_rates": frozenset({"get_by_date", "get_latest_on_or_before", "get_max_date", "save_many"}),
    "coupons": frozenset({"fetch_coupons_for_frontend", "fetch_coupons_raw", "has_coupons_for_secid", "save_moex_coupons"}),
    "kbd": frozenset({"get_kbd_data", "get_last_kbd_date", "save_kbd_records"}),
    "descriptions": frozenset({"get_descriptions_formatted"}),
    "emission_documents": frozenset({"insert_batch"}),
    "emitent_edisclosure": frozenset({"get_edisclosure_id_by_emitent_id", "get_emitents_ordered_by_missing_docs", "get_existing_emitent_ids", "upsert_mapping"}),
    "emitents": frozenset({
        "get_all_emitent_titles", "get_emitent_data_by_secid", "get_emitent_id_by_inn", "get_emitents_with_inn",
        "get_secid_to_emitent_title_index",
    }),
    "events": frozenset({
        "delete_event", "get_by_guid_and_date", "get_event_by_id", "get_existing_types",
        "get_first_unedited_id", "get_navigation_ids", "get_processed_events_keys", "get_stats",
        "save", "save_event_changes",
    }),
    "forecasts": frozenset({"get_all_dates", "get_forecast_by_date", "save_forecast"}),
    "keyrates": frozenset({"get_by_date_range", "get_max_date", "save_many"}),
    "ruonia": frozenset({"get_by_date_range", "get_count", "get_max_date", "save_many"}),
    "trading_history": frozenset({
        "get_by_secid_date_range", "get_first_tradedate", "get_last_tradedate", "save_records",
    }),
}


@lru_cache(maxsize=len(_FACTORIES))
def _get_repository(name: str) -> Any:
    try:
        return _FACTORIES[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown repository: {name}") from exc


def _validate_arguments(method: Any, args: list[Any], kwargs: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    """Validate method inputs from its Python annotations using Pydantic."""
    signature = inspect.signature(method)
    bound = signature.bind(*args, **kwargs)
    try:
        hints = get_type_hints(method)
    except (NameError, TypeError):
        hints = getattr(method, "__annotations__", {})

    for name, value in bound.arguments.items():
        annotation = hints.get(name)
        if annotation is None or annotation is Any or annotation is PydanticUndefined:
            continue
        try:
            bound.arguments[name] = TypeAdapter(annotation).validate_python(value)
        except Exception as exc:
            raise ValueError(f"Invalid value for argument '{name}': {exc}") from exc
    return list(bound.args), dict(bound.kwargs)


def call_repository(payload: RepositoryCall) -> Any:
    """Call one public operation on a service-owned repository instance."""
    if payload.method not in _ALLOWED_OPERATIONS[payload.repository]:
        raise ValueError(f"Repository operation is not available: {payload.repository}.{payload.method}")
    repository = _get_repository(payload.repository)
    method = getattr(repository, payload.method, None)
    if method is None or payload.method.startswith("_") or not callable(method):
        raise ValueError(f"Repository operation is not available: {payload.repository}.{payload.method}")

    args, kwargs = _validate_arguments(method, _decode(payload.args), _decode(payload.kwargs))
    return _encode(method(*args, **kwargs))


__all__ = ["call_repository"]
