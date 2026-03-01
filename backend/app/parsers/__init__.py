"""Парсеры входных данных (Markdown, CSV, HTML и т.д.) в структуры для БД."""

from app.parsers.emission_documents_parser import parse_emission_documents
from app.parsers.forecast_md_parser import (
    ParsedForecast,
    parse_forecast_content,
)

__all__ = [
    "ParsedForecast",
    "parse_emission_documents",
    "parse_forecast_content",
]
