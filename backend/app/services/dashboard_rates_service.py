"""Сервис агрегации макроэкономических показателей для информационной панели.

Модуль консолидирует данные о курсах валют, ставках RUONIA и ключевой ставке
из специализированных сервисов для отображения актуального состояния рынка
на главной странице приложения.
"""

from datetime import date
from typing import Optional

from app.models import MacroRatesDTO
from app.services.currency_service import get_currency_service
from app.services.keyrate_service import get_keyrate_service
from app.services.ruonia_service import get_ruonia_service


def get_dashboard_rates() -> MacroRatesDTO:
    """Собирает сводную информацию о макроэкономических показателях.

    Функция запрашивает последние доступные данные у сервисов валют, RUONIA
    и ключевой ставки. Используется метод получения данных без принудительного
    обновления (чтение из кэша/БД).

    Returns:
        MacroRatesDTO: Объект с актуальными значениями всех индикаторов.

    Raises:
        RuntimeError: Если какой-либо из необходимых сервисов недоступен.
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
