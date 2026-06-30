"""Helpers for bond lifecycle filtering."""

from datetime import date, datetime
from typing import Any, Optional


def parse_maturity_date(value: Any) -> Optional[date]:
    """Parse a MOEX/DB maturity date value into ``date``.

    Empty values and MOEX placeholders are treated as unknown rather than
    expired, so the caller can keep instruments when maturity is missing.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text or text == "0000-00-00":
        return None

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def is_bond_not_matured(
    maturity_date: Any,
    reference_date: Optional[date] = None,
) -> bool:
    """Return True when a bond should remain in active processing.

    A bond with maturity date equal to the reference date is already excluded:
    on the maturity date the investment horizon for the screener is zero.
    Missing or malformed dates are kept to avoid silently dropping incomplete
    MOEX records.
    """
    parsed_maturity = parse_maturity_date(maturity_date)
    if parsed_maturity is None:
        return True

    cutoff = reference_date or date.today()
    return parsed_maturity > cutoff
