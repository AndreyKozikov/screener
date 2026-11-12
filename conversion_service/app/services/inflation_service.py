"""Сервис загрузки и парсинга данных инфляционных ожиданий."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4
from conversion_service.app.repository.db.client import get_db_repository_client
from conversion_service.app.utils.inflation_expectations_parser import (
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
        client = get_db_repository_client()
        response = await asyncio.to_thread(
            client.post,
            "/api/inflation_expectations_update",
            json=data,
        )
        response.raise_for_status()
        return response.json()

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

        client = get_db_repository_client()
        response = await asyncio.to_thread(
            client.post,
            "/api/inflation_data_update",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def download_and_parse_excel(self, url: str) -> Dict[str, Any]:
        """Скачивает Excel-файл инфляционных ожиданий по URL, парсит и после успешной обработки удаляет файл.

        Args:
            url: Прямая ссылка (URL) на Excel-файл.

        Returns:
            Словарь со статусом и распарсенными данными.

        Raises:
            HTTPStatusError: При ошибке загрузки файла по URL.
            FileNotFoundError: Если скачанный файл не найден.
        """
        excel_path = await self._download_excel_by_url(url)
        try:
            return await self.parse_excel(excel_path=excel_path)
        finally:
            self._delete_downloaded_file(excel_path)

    async def download_and_parse_est_infl(self, url: str):
        """Скачивает Excel-файл данных по инфляции по URL, парсит и после успешной обработки удаляет файл.

        Args:
            url: Прямая ссылка (URL) на Excel-файл.

        Returns:
            Словарь со статусом и распарсенными данными.

        Raises:
            HTTPStatusError: При ошибке загрузки файла по URL.
            FileNotFoundError: Если скачанный файл не найден.
        """
        excel_path = await self._download_excel_by_url(url)
        try:
            return await self.parse_est_infl(excel_path=excel_path)
        finally:
            self._delete_downloaded_file(excel_path)

    async def _download_excel_by_url(self, url: str) -> Path:
        """Скачивает Excel-файл по URL во временную директорию сервиса.

        Args:
            url: Прямая ссылка (URL) на Excel-файл.

        Returns:
            Путь к скачанному файлу.

        Raises:
            httpx.HTTPStatusError: При ошибке загрузки файла.
        """
        logger.info("[INFLATION EXPECTATIONS SERVICE] Скачивание файла по URL: %s", url)
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "[INFLATION EXPECTATIONS SERVICE] Ошибка скачивания файла по URL: %s",
                exc,
            )
            raise

        filename = Path(url.split("?")[0]).name or "downloaded.xlsx"
        if not filename.lower().endswith((".xlsx", ".xls")):
            filename += ".xlsx"
        temp_dir = _BASE_SERVICE_DIR / "downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        target_path = temp_dir / f"{Path(filename).stem}_{uuid4().hex[:8]}{Path(filename).suffix}"
        target_path.write_bytes(response.content)
        logger.info("[INFLATION EXPECTATIONS SERVICE] Файл сохранён: %s", target_path)
        return target_path

    def _delete_downloaded_file(self, path: Path) -> None:
        """Удаляет скачанный файл после обработки (best-effort).

        Args:
            path: Путь к скачанному файлу.
        """
        try:
            if path.exists():
                path.unlink()
                logger.info("[INFLATION EXPECTATIONS SERVICE] Скачанный файл удалён: %s", path)
        except OSError as exc:
            logger.warning(
                "[INFLATION EXPECTATIONS SERVICE] Не удалось удалить скачанный файл %s: %s",
                path,
                exc,
            )


_inflation_service_instance: Optional[InflationService] = None


def get_inflation_service():
    """Возвращает синглтон-экземпляр InflationExpectationsService."""
    global _inflation_service_instance
    if _inflation_service_instance is None:
        _inflation_service_instance = InflationService()
    return _inflation_service_instance