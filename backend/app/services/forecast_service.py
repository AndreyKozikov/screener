"""Сервис обработки среднесрочного прогноза Банка России.

После сохранения .md файла эндпоинт передаёт имя файла в этот сервис. Сервис читает
файл из data_dir, парсит через forecast_md_parser, преобразует данные в сущности БД
и сохраняет через ForecastRepository. Только пайплайн: парсинг -> подготовка данных -> вставка.
"""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.entities.forecast import (
    Forecast,
    ForecastBalance,
    ForecastIndicatorName,
    ForecastMainIndicators,
)
from app.models.schemasDTO.forecast_dto import ForecastDatesResponse
from app.parsers.forecast_md_parser import ParsedForecast, parse_forecast_content
from app.repository.db.forecast_repository import ForecastRepository
from app.utils.logger import get_data_update_logger
from config.paths import DATA_DIR, DB_PATH

# Маппинг ключей парсера (основные показатели) -> (min_колонка, max_колонка) в ForecastMainIndicators
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

# Маппинг ключей парсера (платёжный баланс) -> колонка в ForecastBalance
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

SECTION_MAIN = "основные_показатели"
SECTION_BALANCE = "платёжный_баланс"

# Обратный маппинг: колонка БД -> ключ API (для ответа фронту)
_MAIN_COLUMN_TO_KEY: Dict[str, str] = {}
for _key, (_cmin, _cmax) in _MAIN_KEY_TO_COLUMNS.items():
    _MAIN_COLUMN_TO_KEY[_cmin] = _key
    _MAIN_COLUMN_TO_KEY[_cmax] = _key
def _parse_date(s: str) -> date:
    """YYYY-MM-DD -> date."""
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def _parsed_to_meta(parsed: ParsedForecast) -> Forecast:
    """Преобразует даты из ParsedForecast в сущность Forecast."""
    d = _parse_date(parsed.forecast_date)
    m = _parse_date(parsed.meeting_date)
    p = _parse_date(parsed.publication_date)
    return Forecast(date=d, meeting_date=m, publication_date=p)


def _parsed_to_indicator_names(parsed: ParsedForecast) -> List[ForecastIndicatorName]:
    """Собирает список ForecastIndicatorName из names_main и names_balance."""
    out: List[ForecastIndicatorName] = []
    for key, title in parsed.names_main.items():
        out.append(ForecastIndicatorName(section=SECTION_MAIN, key=key, title=title))
    for key, title in parsed.names_balance.items():
        out.append(ForecastIndicatorName(section=SECTION_BALANCE, key=key, title=title))
    return out


def _parsed_to_main_indicators(parsed: ParsedForecast, forecast_date: date) -> List[ForecastMainIndicators]:
    """Преобразует main_indicators из парсера в список ForecastMainIndicators."""
    rows: List[ForecastMainIndicators] = []
    for row in parsed.main_indicators:
        year = row["год"]
        kwargs: Dict[str, Any] = {"forecast_date": forecast_date, "year": year}
        for key, (col_min, col_max) in _MAIN_KEY_TO_COLUMNS.items():
            val = row.get(key)
            if isinstance(val, dict):
                kwargs[col_min] = val.get("мин")
                kwargs[col_max] = val.get("макс")
        rows.append(ForecastMainIndicators(**kwargs))
    return rows


def _parsed_to_balance(parsed: ParsedForecast, forecast_date: date) -> List[ForecastBalance]:
    """Преобразует balance из парсера в список ForecastBalance."""
    rows: List[ForecastBalance] = []
    for row in parsed.balance:
        year = row["год"]
        kwargs: Dict[str, Any] = {"forecast_date": forecast_date, "year": year}
        for key, col in _BALANCE_KEY_TO_COLUMN.items():
            if key in row and row[key] is not None:
                kwargs[col] = row[key]
        rows.append(ForecastBalance(**kwargs))
    return rows


class ForecastService:
    """Оркестрирует парсинг .md файла прогноза и сохранение в БД через репозиторий."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        repository: Optional[ForecastRepository] = None,
    ) -> None:
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._repo = repository or ForecastRepository(db_path=DB_PATH)
        self._log = get_data_update_logger()

    def process_and_save(self, filename: str) -> bool:
        """Читает файл filename из data_dir, парсит, подготавливает данные и сохраняет в БД.

        Args:
            filename: Имя файла в data_dir (например forecast_251024.md).

        Returns:
            True при успешном сохранении.

        Raises:
            FileNotFoundError: Файл не найден.
            ValueError: Ошибка парсинга (нет таблицы или даты).
        """
        path = self._data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Файл прогноза не найден: {path}")

        content = path.read_text(encoding="utf-8")
        parsed = parse_forecast_content(content)

        forecast_date = _parse_date(parsed.forecast_date)
        meta = _parsed_to_meta(parsed)
        indicator_names = _parsed_to_indicator_names(parsed)
        main_indicators = _parsed_to_main_indicators(parsed, forecast_date)
        balance_rows = _parsed_to_balance(parsed, forecast_date)

        ok = self._repo.save_forecast(meta, indicator_names, main_indicators, balance_rows)
        if ok:
            self._log.info("[FORECAST SERVICE] Обработан и сохранён: %s", filename)
        return ok

    def get_available_dates(self) -> ForecastDatesResponse:
        """Запрашивает у репозитория список дат прогнозов, готовит DTO и отдаёт для эндпоинта.

        Репозиторий возвращает сырые данные (list[date]); сервис преобразует в строки
        YYYY-MM-DD и формирует ForecastDatesResponse.
        """
        raw_dates = self._repo.get_all_dates()
        date_strings = [d.isoformat() for d in raw_dates]
        return ForecastDatesResponse(dates=date_strings)

    def get_forecast_data(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает данные прогноза для даты в формате API (date, names, data). Если date_str не указана — последняя доступная дата.

        Raises:
            ValueError: Если дата не найдена в БД.
        """
        if not date_str:
            raw_dates = self._repo.get_all_dates()
            if not raw_dates:
                raise ValueError("No forecast data available")
            date_str = raw_dates[0].isoformat()
        d = _parse_date(date_str)
        raw = self._repo.get_forecast_by_date(d)
        if raw is None:
            raise ValueError(f"Forecast data for date {date_str} not found")
        meta, names_list, main_list, balance_list = raw

        names_main: Dict[str, str] = {}
        names_balance: Dict[str, str] = {}
        for n in names_list:
            if n.section == SECTION_MAIN:
                names_main[n.key] = n.title
            else:
                names_balance[n.key] = n.title

        def _main_row_to_api(row: ForecastMainIndicators) -> Dict[str, Any]:
            out: Dict[str, Any] = {"год": row.year}
            for col_min, col_max in _MAIN_KEY_TO_COLUMNS.values():
                key = _MAIN_COLUMN_TO_KEY.get(col_min)
                if not key:
                    continue
                v_min = getattr(row, col_min, None)
                v_max = getattr(row, col_max, None)
                if v_min is None and v_max is None:
                    continue
                if v_min is not None and v_max is not None and v_min == v_max:
                    out[key] = v_min
                else:
                    out[key] = {"мин": v_min, "макс": v_max}
            return out

        def _balance_row_to_api(row: ForecastBalance) -> Dict[str, Any]:
            out: Dict[str, Any] = {"год": row.year}
            for api_key, col in _BALANCE_KEY_TO_COLUMN.items():
                v = getattr(row, col, None)
                if v is not None:
                    out[api_key] = v
            return out

        main_api = [_main_row_to_api(r) for r in main_list]
        balance_api = [_balance_row_to_api(r) for r in balance_list]

        return {
            "date": date_str,
            "names": {"основные_показатели": names_main, "платёжный_баланс": names_balance},
            "data": {
                "дата_заседания": meta.meeting_date.isoformat(),
                "дата_публикации": meta.publication_date.isoformat(),
                "основные_показатели": main_api,
                "платёжный_баланс": balance_api,
            },
        }


_forecast_service: Optional[ForecastService] = None


def init_forecast_service(
    data_dir: Optional[Path] = None,
    repository: Optional[ForecastRepository] = None,
) -> None:
    """Инициализирует singleton ForecastService."""
    global _forecast_service
    _forecast_service = ForecastService(data_dir=data_dir, repository=repository)


def get_forecast_service() -> ForecastService:
    """Возвращает singleton ForecastService. Перед вызовом нужен init_forecast_service()."""
    if _forecast_service is None:
        init_forecast_service()
    assert _forecast_service is not None
    return _forecast_service
