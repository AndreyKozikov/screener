"""Сервис загрузки и парсинга данных инфляционных ожиданий."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
import httpx
from conversion_service.app.utils.inflation_expectations_parser import (
    JsonDict,
    parse_inflation_expectations_excel,
)
from conversion_service.app.utils.parse_est_infl import parse_est_infl

logger = logging.getLogger(__name__)

# Базовые пути сервиса
_BASE_SERVICE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCEL_PATH: Path = _BASE_SERVICE_DIR / "Infl_exp_26-08.xlsx"


class InflationService:
    """Сервис для парсинга Excel-файла с инфляционными ожиданиями."""

    def __init__(self) -> None:
        self._parse_func = parse_inflation_expectations_excel
        self._parse_est_infl = parse_est_infl

    async def parse_excel(
        self,
        excel_path: Path,
    ) -> Dict[str, Any]:
        """Парсит Excel-файл и возвращает распарсенные данные без сохранения на диск.

        Args:
            excel_path: Путь к файлу Excel

        Returns:
            Словарь со статусом и распарсенными данными.
        """
        source_path = Path(excel_path).resolve() if excel_path else DEFAULT_EXCEL_PATH

        if not source_path.exists():
            raise FileNotFoundError(f"Excel-файл для парсинга не найден: {source_path}")

        logger.info(
            "[INFLATION EXPECTATIONS SERVICE] Запуск парсинга файла: %s",
            source_path,
        )

        # Выполняем синхронный парсинг openpyxl в отдельном потоке
        data = await asyncio.to_thread(self._parse_func, source_path)
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/inflation_expectations_update",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except Exception as e:
            raise

        return result

    async def parse_est_infl(self, excel_path: Path):
        source_path = Path(excel_path).resolve() if excel_path else DEFAULT_EXCEL_PATH

        if not source_path.exists():
            raise FileNotFoundError(f"Excel-файл для парсинга не найден: {source_path}")

        logger.info(
            "[INFLATION EXPECTATIONS SERVICE] Запуск парсинга файла: %s",
            source_path,
        )

        # Выполняем синхронный парсинг openpyxl в отдельном потоке
        data = await asyncio.to_thread(self._parse_est_infl, source_path)

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/inflation_data_update",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except Exception as e:
            raise

        return result


_inflation_service_instance: Optional[InflationService] = None


def get_inflation_service():
    """Возвращает синглтон-экземпляр InflationExpectationsService."""
    global _inflation_service_instance
    if _inflation_service_instance is None:
        _inflation_service_instance = InflationService()
    return _inflation_service_instance