"""Сервис агрегации данных для плашки на главной странице.

Собирает курсы валют, ставку RUONIA и ключевую ставку из соответствующих
сервисов и возвращает единый DTO для одного запроса с фронтенда.
"""

from datetime import date
from typing import Optional

from app.models.macro_rates_dto import MacroRatesDTO
from app.services.currency_service import get_currency_service
from app.services.keyrate_service import get_keyrate_service
from app.services.ruonia_service import get_ruonia_service


def get_dashboard_rates() -> MacroRatesDTO:
    """Формирует данные для плашки главной страницы: курсы валют, RUONIA, ключевая ставка.

    Читает актуальные курсы валют, последнюю ставку RUONIA и ключевую ставку
    на дату не позднее сегодня. Не выполняет обновление данных из внешних API.

    Returns:
        MacroRatesDTO с полями date, source_date, rates, ruonia_rate, key_rate.

    Raises:
        RuntimeError: Если один из сервисов не инициализирован.
    """
    currency_service = get_currency_service()
    ruonia_service = get_ruonia_service()
    keyrate_service = get_keyrate_service()

    currency_dict = currency_service.get_rates(target_date=None, force_refresh=False)

    ruonia_rate_value: Optional[float] = None
    ruonia_response = ruonia_service.get_ruonia_data(date_from=None, date_to=None)
    if ruonia_response.data:
        first_record = ruonia_response.data[0]
        ruonia_rate_value = first_record.stavka_ruonia

    key_rate_value: Optional[float] = None
    keyrate_dict = keyrate_service.get_keyrate_data()
    if keyrate_dict:
        today = date.today()
        closest_date: Optional[str] = None
        min_diff = float("inf")
        for date_str, rate in keyrate_dict.items():
            try:
                d = date.fromisoformat(date_str)
            except ValueError:
                continue
            if d <= today:
                diff = abs((today - d).days)
                if diff < min_diff:
                    min_diff = diff
                    closest_date = date_str
        if closest_date is not None:
            key_rate_value = keyrate_dict[closest_date]

    return MacroRatesDTO.from_services(
        currency_dict=currency_dict,
        ruonia_rate_value=ruonia_rate_value,
        key_rate_value=key_rate_value,
    )
