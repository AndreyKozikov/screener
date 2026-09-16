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

logger = logging.getLogger(__name__)

# Базовые пути сервиса
_BASE_SERVICE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCEL_PATH: Path = _BASE_SERVICE_DIR / "Infl_exp_26-08.xlsx"


class InflationExpectationsService:
    """Сервис для парсинга Excel-файла с инфляционными ожиданиями."""

    def __init__(
        self,
        parse_func: Optional[Callable[[Union[str, Path]], JsonDict]] = None,
    ) -> None:
        self._parse_func = parse_func or parse_inflation_expectations_excel

    async def parse_excel(
        self,
        excel_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Парсит Excel-файл и возвращает распарсенные данные без сохранения на диск.

        Args:
            excel_path: Путь к файлу Excel. Если не указан, используется DEFAULT_EXCEL_PATH.

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

        return {
            "status": "ok"
        }


_inflation_expectations_service_instance: Optional[InflationExpectationsService] = None


def get_inflation_expectations_service() -> InflationExpectationsService:
    """Возвращает синглтон-экземпляр InflationExpectationsService."""
    global _inflation_expectations_service_instance
    if _inflation_expectations_service_instance is None:
        _inflation_expectations_service_instance = InflationExpectationsService()
    return _inflation_expectations_service_instance