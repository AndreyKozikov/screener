"""Read-only access to key-rate records in the shared database."""

from datetime import date
from typing import List, Optional

from app.models import KeyrateDTO
from app.repository.db.keyrate_repository import KeyrateRepository


class KeyRateService:
    """Expose key-rate queries to backend features without performing updates."""

    def __init__(self, repository: Optional[KeyrateRepository] = None) -> None:
        self._repository = repository or KeyrateRepository()

    def get_keyrate_data(self) -> dict[str, float]:
        records = self._repository.get_by_date_range(from_date=None, till_date=None)
        return {
            _date_key(row.dt): float(row.rate)
            for row in records
            if row.dt is not None and row.rate is not None
        }

    def get_keyrate_list(
        self,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> List[KeyrateDTO]:
        records = self._repository.get_by_date_range(
            from_date=from_date,
            till_date=till_date,
        )
        return [KeyrateDTO(dt=row.dt, rate=row.rate) for row in records]


def _date_key(value: date) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


_keyrate_service: Optional[KeyRateService] = None


def get_keyrate_service() -> KeyRateService:
    global _keyrate_service
    if _keyrate_service is None:
        _keyrate_service = KeyRateService()
    return _keyrate_service
