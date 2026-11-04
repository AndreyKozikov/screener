"""Read-only access to currency rates stored in the shared database."""

from datetime import date
from typing import Any, Dict, Optional

from app.repository.db.currencyrate_repository import CurrencyrateRepository


class CurrencyService:
    """Read the nearest available currency-rate row without refreshing it."""

    def __init__(self, repository: Optional[CurrencyrateRepository] = None) -> None:
        self._repository = repository or CurrencyrateRepository()

    def get_rates(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        target_date = target_date or date.today()
        row = self._repository.get_by_date(target_date)
        if row is None:
            row = self._repository.get_latest_on_or_before(target_date)
        if row is None:
            return {"date": target_date.isoformat(), "source_date": "", "rates": {}}

        rates = {}
        for code, value, nominal, original in (
            ("USD", row.usd_rate, row.usd_nominal, row.usd_original_value),
            ("EUR", row.eur_rate, row.eur_nominal, row.eur_original_value),
            ("CNY", row.cny_rate, row.cny_nominal, row.cny_original_value),
        ):
            if value is not None:
                rates[code] = {
                    "code": code,
                    "rate": value,
                    "nominal": nominal or 1,
                    "original_value": original or "",
                }
        return {
            "date": _date_key(row.dt),
            "source_date": row.source_date or "",
            "rates": rates,
        }


def _date_key(value: date) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


_currency_service: Optional[CurrencyService] = None


def get_currency_service() -> CurrencyService:
    global _currency_service
    if _currency_service is None:
        _currency_service = CurrencyService()
    return _currency_service
