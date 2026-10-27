"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import TradingHistoryRepository as TradingHistoryRepository

__all__ = ["TradingHistoryRepository"]
