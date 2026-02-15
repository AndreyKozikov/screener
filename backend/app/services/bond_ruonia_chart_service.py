"""Сервис для формирования данных графика сравнения доходности облигации и RUONIA.

Использует RuoniaService и TradingHistoryService; не обращается к репозиториям напрямую.
Период: от (текущая дата минус 1 день) на год назад.
Нормализация: только даты, присутствующие в обеих таблицах.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from app.models import BondYieldRuoniaChartItem, BondYieldRuoniaChartResponse
from app.services.ruonia_service import get_ruonia_service
from app.services.trading_history_service import get_trading_history_service


def _date_to_dd_mm_yyyy(d: date) -> str:
    """Форматирует date в строку DD.MM.YYYY для RuoniaService.get_ruonia_data."""
    return d.strftime("%d.%m.%Y")


def get_yield_ruonia_chart_data(secid: str) -> BondYieldRuoniaChartResponse:
    """Формирует нормализованные данные для графика доходность облигации vs RUONIA.

    Период: от (сегодня - 1 день) минус 1 год до (сегодня - 1 день).
    В ответ попадают только даты, по которым есть и ставка RUONIA, и доходность
    облигации (yieldatwap).

    Args:
        secid: Идентификатор облигации (SECID).

    Returns:
        BondYieldRuoniaChartResponse с полем data — список точек по датам.
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
