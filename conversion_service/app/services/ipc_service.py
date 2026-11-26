"""Сервис загрузки, парсинга и сохранения данных ИПЦ Росстата."""

import asyncio
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4

import requests

from conversion_service.app.repository.db.client import get_db_repository_client
from conversion_service.app.repository.files.file_storage import FileStorage
from conversion_service.app.utils.ipc_excel_parser import IpcExcelParser
from conversion_service.app.utils.rosstat_ipc_reports_parser import get_ipc_weekly

logger = logging.getLogger(__name__)

# Базовые пути сервиса
_BASE_SERVICE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCEL_PATH: Path = _BASE_SERVICE_DIR / "ipc_RF_fo_sub_08-2026.xlsx"
DEFAULT_OUTPUT_PATH: Path = _BASE_SERVICE_DIR / "ipc_data.json"

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

class IpcService:


    def __init__(
        self,
        parser: Optional[IpcExcelParser] = None,
        file_storage: Optional[FileStorage] = None,
    ) -> None:
        self._parser = parser or IpcExcelParser()
        self._file_storage = file_storage or FileStorage()

    async def parse_and_save(
        self,
        excel_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Парсит Excel-файл и сохраняет извлечённые данные в JSON-файл.

        Args:
            excel_path: Путь к файлу Excel. Если не указан, используется DEFAULT_EXCEL_PATH.
            output_path: Путь к результирующему JSON. Если не указан, используется DEFAULT_OUTPUT_PATH.

        Returns:
            Словарь со статусом, путём файла, статистикой и распарсенными данными.
        """
        source_path = Path(excel_path).resolve() if excel_path else DEFAULT_EXCEL_PATH
        target_output = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT_PATH

        if not source_path.exists():
            raise FileNotFoundError(f"Excel-файл для парсинга не найден: {source_path}")

        logger.info("[IPC SERVICE] Запуск парсинга файла: %s", source_path)

        # Выполняем синхронный парсинг openpyxl в отдельном потоке
        data = await asyncio.to_thread(self._parser.parse_file, source_path)

        # Сохраняем результат в JSON с форматированием
        logger.info("[IPC SERVICE] Сохранение результата в JSON: %s", target_output)

        #self._file_storage.write_json_durable(target_output, data, indent=True, append_newline=True)

        try:
            client = get_db_repository_client()
            response = await asyncio.to_thread(
                client.post,
                "/api/ipc_update",
                json=data,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            raise

        return result

    async def download_parse_and_save(self, url: str) -> Dict[str, Any]:
        """Скачивает Excel-файл ИПЦ по URL, парсит и сохраняет данные в БД.

        После обработки скачанный файл удаляется.
        """
        excel_path = await asyncio.to_thread(self._download_excel_by_url, url)
        try:
            return await self.parse_and_save(excel_path=excel_path)
        finally:
            self._delete_downloaded_file(excel_path)

    def _download_excel_by_url(self, url: str) -> Path:
        """Скачивает Excel-файл по URL во временную директорию сервиса."""
        if not url.startswith(("http://", "https://")):
            raise ValueError("Ссылка должна начинаться с http:// или https://")

        logger.info("[IPC SERVICE] Скачивание файла по URL: %s", url)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = requests.get(
                url,
                headers=_DOWNLOAD_HEADERS,
                verify=False,
                timeout=120,
            )

        response.raise_for_status()

        filename = Path(url.split("?")[0]).name or "ipc.xlsx"
        if not filename.lower().endswith((".xlsx", ".xls")):
            filename += ".xlsx"

        temp_dir = _BASE_SERVICE_DIR / "downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        target_path = temp_dir / (
            f"{Path(filename).stem}_{uuid4().hex[:8]}{Path(filename).suffix}"
        )
        target_path.write_bytes(response.content)
        logger.info("[IPC SERVICE] Файл сохранён: %s", target_path)
        return target_path

    @staticmethod
    def _delete_downloaded_file(path: Path) -> None:
        """Удаляет скачанный файл после обработки (best-effort)."""
        try:
            if path.exists():
                path.unlink()
                logger.info("[IPC SERVICE] Скачанный файл удалён: %s", path)
        except OSError as exc:
            logger.warning("[IPC SERVICE] Не удалось удалить файл %s: %s", path, exc)

    async def upload_and_parce_ipc_weekly_reports(self):
        data = get_ipc_weekly()
        print(data)
        try:
            client = get_db_repository_client()
            response = await asyncio.to_thread(
                client.post,
                "/api/ipc_weekly_update",
                json=data,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            raise

        return result



_ipc_service_instance: Optional[IpcService] = None


def get_ipc_service() -> IpcService:
    """Возвращает синглтон-экземпляр IpcService."""
    global _ipc_service_instance
    if _ipc_service_instance is None:
        _ipc_service_instance = IpcService()
    return _ipc_service_instance
