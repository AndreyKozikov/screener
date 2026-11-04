"""Aggregate market rates from the shared database for the dashboard."""

from datetime import date
from typing import Optional

from app.models import MacroRatesDTO
from app.repository.db.currencyrate_repository import CurrencyrateRepository
from app.repository.db.keyrate_repository import KeyrateRepository
from app.repository.db.ruonia_repository import RuoniaRepository


def get_dashboard_rates() -> MacroRatesDTO:
    today = date.today()
    currency_repository = CurrencyrateRepository()
    currency_row = currency_repository.get_by_date(today)
    if currency_row is None:
        currency_row = currency_repository.get_latest_on_or_before(today)
    currency_dict = _currency_row_to_api_dict(currency_row, today)

    ruonia_rows = RuoniaRepository().get_by_date_range()
    ruonia_rate_value: Optional[float] = ruonia_rows[0].ruo if ruonia_rows else None

    key_rate_value: Optional[float] = None
    keyrate_rows = KeyrateRepository().get_by_date_range()
    for row in keyrate_rows:
        if row.dt <= today:
            key_rate_value = row.rate
            break

    return MacroRatesDTO.from_services(
        currency_dict=currency_dict,
        ruonia_rate_value=ruonia_rate_value,
        key_rate_value=key_rate_value,
    )


def _currency_row_to_api_dict(row, target_date: date) -> dict:
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
        "date": row.dt.isoformat() if hasattr(row.dt, "isoformat") else str(row.dt),
        "source_date": row.source_date or "",
        "rates": rates,
    }
