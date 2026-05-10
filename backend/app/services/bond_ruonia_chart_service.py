"""Сервис формирования данных для визуализации доходности облигаций относительно RUONIA.

Модуль агрегирует исторические значения ставок RUONIA и рыночную доходность облигаций,
обеспечивая их синхронизацию по датам для построения корректных сравнительных графиков.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from app.models import BondYieldRuoniaChartItem, BondYieldRuoniaChartResponse
from app.services.ruonia_service import get_ruonia_service
from app.services.trading_history_service import get_trading_history_service


def _date_to_dd_mm_yyyy(d: date) -> str:
    """Преобразует объект даты в строковый формат DD.MM.YYYY.

    Данный формат требуется для корректной работы метода get_ruonia_data сервиса RuoniaService.

    Args:
        d (date): Объект даты для преобразования.

    Returns:
        str: Строка с датой в формате 'ДД.ММ.ГГГГ'.
    """
    return d.strftime("%d.%m.%Y")


def get_yield_ruonia_chart_data(secid: str) -> BondYieldRuoniaChartResponse:
    """Формирует набор данных для построения графика сравнения доходности облигации и RUONIA.

    Метод запрашивает историю торгов облигации (взвешенная доходность yieldatwap) и историю
    ставок RUONIA за последний год. Результат содержит только точки пересечения, где оба
    значения не являются пустыми.

    Args:
        secid (str): Идентификатор ценной бумаги (SECID).

    Returns:
        BondYieldRuoniaChartResponse: Объект ответа, содержащий список точек данных для графика.
    """
    secid = (secid or "").strip()
    if not secid:
        return BondYieldRuoniaChartResponse(secid=secid, data=[])

    date_to = date.today() - timedelta(days=1)
    date_from = date_to - timedelta(days=365)

    ruonia_service = get_ruonia_service()
    trading_service = get_trading_history_service()

    ruonia_response = ruonia_service.get_ruonia_data(
        date_from=_date_to_dd_mm_yyyy(date_from),
        date_to=_date_to_dd_mm_yyyy(date_to),
    )
    bond_points: List[Tuple[date, Optional[float]]] = trading_service.get_history_for_period(
        secid=secid,
        date_from=date_from,
        date_to=date_to,
    )

    # Словари дата -> значение (даты в RUONIA в формате YYYY-MM-DD в date_stavki)
    ruonia_by_date: Dict[date, Optional[float]] = {}
    for dto in ruonia_response.data:
        try:
            d = date.fromisoformat(dto.date_stavki)
            ruonia_by_date[d] = dto.stavka_ruonia
        except (ValueError, TypeError):
            continue

    bond_by_date: Dict[date, Optional[float]] = {d: y for d, y in bond_points}

    # Пересечение дат
    common_dates = sorted(set(ruonia_by_date.keys()) & set(bond_by_date.keys()))

    data = [
        BondYieldRuoniaChartItem(
            date=d.isoformat(),
            ruonia_rate=ruonia_by_date.get(d),
            yieldatwap=bond_by_date.get(d),
        )
        for d in common_dates
    ]

    return BondYieldRuoniaChartResponse(secid=secid, data=data)
