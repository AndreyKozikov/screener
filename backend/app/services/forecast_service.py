"""Read-only service for stored Bank of Russia forecasts."""

from datetime import date
from typing import Any, Dict, List, Optional

from app.models.schemasDTO.forecast_dto import ForecastDatesResponse
from app.repository.db.forecast_repository import ForecastRepository

_MAIN_KEY_TO_COLUMNS: Dict[str, tuple[str, str]] = {
    "инфляция_декабрь_к_декабрю": ("inflation_dec_min", "inflation_dec_max"),
    "инфляция_среднегодовая": ("inflation_avg_min", "inflation_avg_max"),
    "ключевая_ставка_средняя": ("key_rate_min", "key_rate_max"),
    "ввп": ("gdp_min", "gdp_max"),
    "ввп_q4_q4": ("gdp_q4_min", "gdp_q4_max"),
    "расходы_конечного_потребления": ("consumption_min", "consumption_max"),
    "расходы_домохозяйств": ("household_consumption_min", "household_consumption_max"),
    "валовое_накопление": ("accumulation_min", "accumulation_max"),
    "накопление_основного_капитала": ("capital_accumulation_min", "capital_accumulation_max"),
    "экспорт": ("export_min", "export_max"),
    "импорт": ("import_min", "import_max"),
    "денежная_масса": ("money_supply_min", "money_supply_max"),
    "требования_к_экономике": ("claims_economy_min", "claims_economy_max"),
    "требования_к_организациям": ("claims_orgs_min", "claims_orgs_max"),
    "требования_к_населению": ("claims_households_min", "claims_households_max"),
    "ипотечные_кредиты": ("mortgage_loans_min", "mortgage_loans_max"),
}

_BALANCE_KEY_TO_COLUMN: Dict[str, str] = {
    "счёт_текущих_операций": "account_current_operations",
    "торговый_баланс": "trade_balance",
    "товарный_экспорт": "goods_export",
    "товарный_импорт": "goods_import",
    "баланс_услуг": "services_balance",
    "экспорт_услуг": "services_export",
    "импорт_услуг": "services_import",
    "баланс_доходов": "income_balance",
    "финансовый_счёт": "financial_account",
    "принятие_обязательств": "liabilities_net",
    "приобретение_финансовых_активов": "assets_net",
    "ошибки_и_пропуски": "errors_omissions",
    "изменение_резервов": "reserves_change",
    "цена_нефти": "oil_price",
}

_MAIN_COLUMN_TO_KEY: Dict[str, str] = {}
for _key, (_min_col, _max_col) in _MAIN_KEY_TO_COLUMNS.items():
    _MAIN_COLUMN_TO_KEY[_min_col] = _key
    _MAIN_COLUMN_TO_KEY[_max_col] = _key


def _parse_date(value: str) -> date:
    return date(int(value[0:4]), int(value[5:7]), int(value[8:10]))


class ForecastService:
    """Expose stored forecasts without performing imports or writes."""

    def __init__(self, repository: Optional[ForecastRepository] = None) -> None:
        self._repo = repository or ForecastRepository()

    def get_available_dates(self) -> ForecastDatesResponse:
        dates = self._repo.get_all_dates()
        return ForecastDatesResponse(dates=[item.isoformat() for item in dates])

    def get_forecast_data(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        if not date_str:
            dates = self._repo.get_all_dates()
            if not dates:
                raise ValueError("No forecast data available")
            date_str = dates[0].isoformat()
        raw = self._repo.get_forecast_by_date(_parse_date(date_str))
        if raw is None:
            raise ValueError(f"Forecast data for date {date_str} not found")
        meta, names_list, main_list, balance_list = raw

        names_main: Dict[str, str] = {}
        names_balance: Dict[str, str] = {}
        for item in names_list:
            if item.section == "основные_показатели":
                names_main[item.key] = item.title
            else:
                names_balance[item.key] = item.title

        def main_row_to_api(row: Any) -> Dict[str, Any]:
            result: Dict[str, Any] = {"год": row.year}
            for col_min, col_max in _MAIN_KEY_TO_COLUMNS.values():
                key = _MAIN_COLUMN_TO_KEY.get(col_min)
                if not key:
                    continue
                value_min = getattr(row, col_min, None)
                value_max = getattr(row, col_max, None)
                if value_min is None and value_max is None:
                    continue
                if value_min is not None and value_max is not None and value_min == value_max:
                    result[key] = value_min
                else:
                    result[key] = {"мин": value_min, "макс": value_max}
            return result

        def balance_row_to_api(row: Any) -> Dict[str, Any]:
            result: Dict[str, Any] = {"год": row.year}
            for key, column in _BALANCE_KEY_TO_COLUMN.items():
                value = getattr(row, column, None)
                if value is not None:
                    result[key] = value
            return result

        return {
            "date": date_str,
            "names": {
                "основные_показатели": names_main,
                "платёжный_баланс": names_balance,
            },
            "data": {
                "дата_заседания": meta.meeting_date.isoformat(),
                "дата_публикации": meta.publication_date.isoformat(),
                "основные_показатели": [main_row_to_api(row) for row in main_list],
                "платёжный_баланс": [balance_row_to_api(row) for row in balance_list],
            },
        }


_forecast_service: Optional[ForecastService] = None


def get_forecast_service() -> ForecastService:
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = ForecastService()
    return _forecast_service
