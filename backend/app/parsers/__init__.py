"""Парсеры входных данных (Markdown, CSV и т.д.) в структуры для БД."""

from app.parsers.forecast_md_parser import (
    ParsedForecast,
    parse_forecast_content,
)

__all__ = [
    "ParsedForecast",
    "parse_forecast_content",
]
