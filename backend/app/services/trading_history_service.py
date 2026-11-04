"""Read-only queries for stored bond trading history."""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.repository.db.trading_history_repository import TradingHistoryRepository

DEFAULT_FROM_DATE: date = date(2000, 1, 1)


class TradingHistoryService:
    """Query stored trading history for charts."""

    def __init__(self, history_repository: Optional[TradingHistoryRepository] = None) -> None:
        self._history_repo = history_repository or TradingHistoryRepository()

    def get_first_tradedate(self, secid: str) -> Optional[date]:
        return self._history_repo.get_first_tradedate(secid.strip())

    def get_history_for_period(
        self,
        secid: str,
        date_from: date,
        date_to: date,
    ) -> List[Tuple[date, Optional[float]]]:
        records = self._history_repo.get_by_secid_date_range(
            secid=secid.strip(),
            date_from=date_from,
            date_to=date_to,
        )
        by_date: Dict[date, Optional[float]] = {}
        for record in records:
            if record.tradedate not in by_date or by_date[record.tradedate] is None:
                by_date[record.tradedate] = record.yieldatwap
        return [(day, by_date[day]) for day in sorted(by_date)]

    def get_price_history(self, secid: str) -> List[Dict[str, Any]]:
        records = self._history_repo.get_by_secid_date_range(
            secid=secid.strip(),
            date_from=DEFAULT_FROM_DATE,
            date_to=date.today(),
        )
        by_date: Dict[date, Optional[float]] = {}
        for record in records:
            if record.tradedate not in by_date or by_date[record.tradedate] is None:
                if record.open is not None:
                    by_date[record.tradedate] = record.open
        return [{"date": day, "open": by_date[day]} for day in sorted(by_date)]


_trading_history_service: Optional[TradingHistoryService] = None


def get_trading_history_service() -> TradingHistoryService:
    global _trading_history_service
    if _trading_history_service is None:
        _trading_history_service = TradingHistoryService()
    return _trading_history_service
