"""Загрузка сделок по облигациям из выбранного сохранённого портфеля."""

from __future__ import annotations

from typing import Any

from app.repository.db.remote_repository import PortfolioImportRepository


class PortfolioDealsService:
    """Читает сделки по бумагам, которые есть в закрывающем снимке портфеля."""

    def __init__(self, repository: PortfolioImportRepository | None = None) -> None:
        self._repository = repository or PortfolioImportRepository()

    def get_current_portfolio_deals(
        self, user_id: str, portfolio_id: int
    ) -> dict[str, Any] | None:
        portfolio = self._repository.get_current_positions_for_user(user_id, portfolio_id)
        if portfolio is None:
            return None

        deals = self._repository.get_current_position_trades_for_user(user_id, portfolio_id)
        return {
            "portfolio_id": portfolio["portfolio_id"],
            "portfolio_name": portfolio["portfolio_name"],
            "base_currency": portfolio["base_currency"],
            "deals": deals,
        }


__all__ = ["PortfolioDealsService"]
