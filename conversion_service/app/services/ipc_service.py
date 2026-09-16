"""Сервис загрузки, парсинга и сохранения данных ИПЦ Росстата."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx

from conversion_service.app.repository.files.file_storage import FileStorage
from conversion_service.app.utils.ipc_excel_parser import IpcExcelParser
from conversion_service.app.utils.rosstat_ipc_reports_parser import get_ipc_weekly

logger = logging.getLogger(__name__)

# Базовые пути сервиса
_BASE_SERVICE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCEL_PATH: Path = _BASE_SERVICE_DIR / "ipc_RF_fo_sub_08-2026.xlsx"
DEFAULT_OUTPUT_PATH: Path = _BASE_SERVICE_DIR / "ipc_data.json"

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
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/ipc_update",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except Exception as e:
            raise

        return result

    async def upload_and_parce_ipc_weekly_reports(self):
        data = get_ipc_weekly()
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api//ipc_weekly_update",
                    json=data,
                    headers={"Content-Type": "application/json"},
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
