"""Run one of the conversion service's existing data refresh operations."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any, Callable

_MAX_LOG_KEYS = 30
_MAX_LOG_STRING = 300


def _summarize(value: Any, depth: int = 0) -> Any:
    """Keep scheduler logs useful without dumping market-data payloads."""
    if isinstance(value, dict):
        summary = {
            str(key): _summarize(item, depth + 1)
            for key, item in list(value.items())[:_MAX_LOG_KEYS]
        }
        if len(value) > _MAX_LOG_KEYS:
            summary["_omitted_keys"] = len(value) - _MAX_LOG_KEYS
        return summary
    if isinstance(value, (list, tuple)):
        if depth >= 2 or len(value) > 5:
            return f"<{len(value)} items>"
        return [_summarize(item, depth + 1) for item in value]
    if isinstance(value, str) and len(value) > _MAX_LOG_STRING:
        return value[:_MAX_LOG_STRING] + f"… <{len(value) - _MAX_LOG_STRING} chars omitted>"
    return value


def _run(task: str) -> Any:
    if task == "bonds":
        from conversion_service.app.services.bonds_service import get_bonds_update_service

        return asyncio.run(get_bonds_update_service().update_bonds_data())
    if task == "trading_history":
        from conversion_service.app.services.trading_history_update_service import get_trading_history_service

        return get_trading_history_service().download_history_all()
    if task == "zerocupon":
        from conversion_service.app.services.zerocupon_update_service import get_zerocupon_update_service

        return get_zerocupon_update_service().refresh()
    if task == "currency":
        from conversion_service.app.services.currency_update_service import get_currency_service

        return get_currency_service().refresh_rates()
    if task == "ruonia":
        from conversion_service.app.services.ruonia_update_service import get_ruonia_service

        return get_ruonia_service().update_ruonia_data()
    if task == "keyrate":
        from conversion_service.app.services.keyrate_update_service import get_keyrate_service

        return get_keyrate_service().load_keyrate_data()
    if task == "inflation_expectations":
        from conversion_service.app.services.inflation_expectations_update_service import (
            get_inflation_expectations_update_service,
        )

        return asyncio.run(get_inflation_expectations_update_service().run())
    raise ValueError(f"Unknown update task: {task}")


def _ensure_success(task: str, result: Any) -> None:
    """Treat explicit service error results and partial history failures as failures."""
    if isinstance(result, dict):
        if str(result.get("status", "")).lower() == "error":
            raise RuntimeError(result.get("error") or result.get("message") or "Service reported an error")
        if task == "trading_history" and (result.get("failed", 0) or result.get("errors")):
            failed = result.get("failed", len(result.get("errors") or []))
            sample = _summarize((result.get("errors") or [])[:5])
            raise RuntimeError(
                f"Trading history partially failed: failed={failed}, "
                f"total={result.get('total')}, sample_errors={sample}"
            )


def run_task(task: str, runner: Callable[[str], Any] = _run) -> Any:
    result = runner(task)
    _ensure_success(task, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "task",
        choices=(
            "bonds",
            "trading_history",
            "zerocupon",
            "currency",
            "ruonia",
            "keyrate",
            "inflation_expectations",
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        result = run_task(args.task)
        status = result.get("status") if isinstance(result, dict) else None
        summary = json.dumps(_summarize(result), ensure_ascii=False, default=str)
        logging.getLogger(__name__).info(
            "Task %s finished with status %s: %s",
            args.task,
            status or "ok",
            summary,
        )
        return 3 if status == "not_completed" else 0
    except Exception:
        logging.getLogger(__name__).exception("Scheduled task %s failed", args.task)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
