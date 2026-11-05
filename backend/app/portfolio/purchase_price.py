"""Average purchase price from imported report trades."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


def calculate_average_purchase_price(
    trades: Iterable[dict[str, Any]], current_quantity: int
) -> Decimal | None:
    """Return weighted average clean buy price (% of nominal) when history is complete.

    Sells reduce the cost basis at the current average. If the report does not
    contain enough history to account for the closing quantity, no estimate is
    returned.
    """
    held_quantity = 0
    total_cost = Decimal("0")

    for trade in sorted(
        trades,
        key=lambda item: (item.get("trade_date") or "", item.get("id") or 0),
    ):
        try:
            quantity = int(trade.get("quantity") or 0)
        except (TypeError, ValueError):
            return None
        if quantity <= 0:
            continue

        operation = str(trade.get("operation_type") or "").upper()
        if operation == "BUY":
            raw_price = trade.get("price_percent_scaled")
            if raw_price is None:
                return None
            try:
                price = Decimal(str(raw_price)) / Decimal(10_000)
            except (InvalidOperation, TypeError, ValueError):
                return None
            total_cost += Decimal(quantity) * price
            held_quantity += quantity
        elif operation == "SELL":
            if quantity > held_quantity:
                return None
            if held_quantity:
                average = total_cost / Decimal(held_quantity)
                total_cost -= average * Decimal(quantity)
            held_quantity -= quantity

    if held_quantity <= 0 or held_quantity != current_quantity:
        return None
    return total_cost / Decimal(held_quantity)

