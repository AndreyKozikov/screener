"""Fetch each dashboard source once through the existing backend services."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.schemasDTO.inflations_dto import InflationDateFilter
from app.services.inflations import get_inflation_service
from app.services.ipc_service import get_ipc_service
from app.services.kbd_service import get_kbd_service
from app.services.keyrate_service import get_keyrate_service
from app.services.ruonia_service import get_ruonia_service


def _plain_rows(rows: Any) -> list[dict[str, Any]]:
    if not rows:
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            result.append(row)
        elif hasattr(row, "model_dump"):
            result.append(row.model_dump(mode="json", by_alias=False))
        elif hasattr(row, "__dict__"):
            result.append({key: value for key, value in vars(row).items() if not key.startswith("_")})
    return result


@dataclass
class MacroRawData:
    keyrates: list[dict[str, Any]] = field(default_factory=list)
    ruonia: list[dict[str, Any]] = field(default_factory=list)
    ipc_monthly: list[dict[str, Any]] = field(default_factory=list)
    ipc_weekly: list[dict[str, Any]] = field(default_factory=list)
    expectations: list[dict[str, Any]] = field(default_factory=list)
    sustainable_inflation: list[dict[str, Any]] = field(default_factory=list)
    yield_curve: list[dict[str, Any]] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class DataProvider:
    """Collect source data through existing services without storing derived values."""

    async def fetch(self) -> MacroRawData:
        async def optional_async(name: str, call: Callable[[], Any]) -> Any:
            try:
                return await call()
            except Exception as exc:  # a source outage should not hide unrelated indicators
                errors[name] = str(exc)
                return None

        async def optional_sync(name: str, call: Callable[[], Any]) -> Any:
            try:
                return await asyncio.to_thread(call)
            except Exception as exc:
                errors[name] = str(exc)
                return None

        errors: dict[str, str] = {}
        empty_filter = InflationDateFilter()
        requests = {
            "keyrates": optional_sync(
                "keyrate", lambda: get_keyrate_service().get_keyrate_list()
            ),
            "ruonia": optional_sync(
                "ruonia",
                lambda: get_ruonia_service().get_ruonia_data().data,
            ),
            "ipc": optional_async("ipc", lambda: get_ipc_service().get_data()),
            "expectations": optional_async(
                "expectations", lambda: get_inflation_service().get_inflation_data(empty_filter)
            ),
            "sustainable": optional_async(
                "sustainable_inflation",
                lambda: get_inflation_service().get_sustainable_inflation_data(empty_filter),
            ),
            "yield_curve": optional_sync(
                "yield_curve",
                lambda: get_kbd_service().get_kbd_data_formatted(
                    date_from=None, date_to=None
                ) if get_kbd_service() is not None else [],
            ),
        }
        results = await asyncio.gather(*requests.values())
        fetched = dict(zip(requests.keys(), results))

        ipc = fetched.get("ipc") or {}
        return MacroRawData(
            keyrates=_plain_rows(fetched.get("keyrates")),
            ruonia=_plain_rows(fetched.get("ruonia")),
            ipc_monthly=_plain_rows(ipc.get("monthly", [])) if isinstance(ipc, dict) else [],
            ipc_weekly=_plain_rows(ipc.get("weekly", [])) if isinstance(ipc, dict) else [],
            expectations=_plain_rows(fetched.get("expectations")),
            sustainable_inflation=_plain_rows(fetched.get("sustainable")),
            yield_curve=_plain_rows(fetched.get("yield_curve")),
            errors=errors,
        )
