"""Сервис конвертации PDF в Markdown через внешний API.

Отправляет PDF-файлы из data-директории на внешний PDF2MD сервис,
сохраняет полученный Markdown через FileStorage и дополняет результирующий
словарь списком созданных .md файлов.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.repository.files.file_storage import FileStorage
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

_TIMEOUT: float = 600.0


class PdfConversionService:
    """Конвертирует PDF-документы в Markdown через внешний PDF2MD API.

    Работает синхронно. Выбирает single/batch endpoint в зависимости
    от количества файлов. Результаты (.md) сохраняются через FileStorage.
    """

    def __init__(
        self,
        file_storage: Optional[FileStorage] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._file_storage: FileStorage = file_storage or FileStorage()
        self._base_url: str = (base_url or settings.PDF2MD_BASE_URL).rstrip("/")

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертирует PDF-файлы из *data* и добавляет ключ ``md_filenames``.

        Args:
            data: Словарь, содержащий ключ ``doc_filenames`` со списком
                имён PDF-файлов в data-директории.

        Returns:
            Копия *data* с добавленным ключом ``md_filenames: List[str]``.
        """
        doc_filenames: List[str] = data.get("doc_filenames", [])

        if not doc_filenames:
            return {**data, "md_filenames": []}

        if len(doc_filenames) == 1:
            md_filenames = self._convert_single(doc_filenames[0])
        else:
            md_filenames = self._convert_batch(doc_filenames)

        return {**data, "md_filenames": md_filenames}

    def _convert_single(self, filename: str) -> List[str]:
        """Конвертирует один PDF через ``/api/v1/convert``.

        Args:
            filename: Имя PDF-файла в data-директории.

        Returns:
            Список из одного имени .md файла при успехе, иначе пустой список.
        """
        file_path: Path = _DATA_DIR / filename
        if not file_path.is_file():
            logger.error("PDF файл не найден: %s", file_path)
            return []

        url: str = f"{self._base_url}/api/v1/convert"
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                with open(file_path, "rb") as f:
                    response: httpx.Response = client.post(
                        url,
                        files={"file": (filename, f, "application/pdf")},
                    )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Ошибка при конвертации %s: %s", filename, exc)
            return []

        body: Dict[str, Any] = response.json()
        markdown: Optional[str] = body.get("markdown")
        if not markdown:
            logger.warning("Пустой markdown в ответе для %s", filename)
            return []

        md_filename: str = Path(filename).stem + ".md"
        self._file_storage.save_text_file(_DATA_DIR / md_filename, markdown)
        logger.info("Сохранён markdown: %s", _DATA_DIR / md_filename)
        return [md_filename]

    def _convert_batch(self, filenames: List[str]) -> List[str]:
        """Конвертирует несколько PDF через ``/api/v1/convert/batch``.

        Args:
            filenames: Имена PDF-файлов в data-директории.

        Returns:
            Список имён успешно созданных .md файлов.
        """
        files_payload: List[Tuple[str, Tuple[str, bytes, str]]] = []
        for filename in filenames:
            file_path: Path = _DATA_DIR / filename
            if not file_path.is_file():
                logger.error("PDF файл не найден, пропуск: %s", file_path)
                continue
            files_payload.append(
                ("files", (filename, file_path.read_bytes(), "application/pdf")),
            )

        if not files_payload:
            return []

        url: str = f"{self._base_url}/api/v1/convert/batch"
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response: httpx.Response = client.post(url, files=files_payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Ошибка batch-конвертации: %s", exc)
            return []

        body: Dict[str, Any] = response.json()
        results: List[Dict[str, Any]] = body.get("results", [])

        md_filenames: List[str] = []
        for item in results:
            original: str = item.get("filename", "")
            error: Optional[str] = item.get("error")
            markdown: Optional[str] = item.get("markdown")

            if error:
                logger.error("Ошибка конвертации %s: %s", original, error)
                continue

            if not markdown:
                logger.warning("Пустой markdown для %s", original)
                continue

            md_filename: str = Path(original).stem + ".md"
            self._file_storage.save_text_file(_DATA_DIR / md_filename, markdown)
            logger.info("Сохранён markdown: %s", _DATA_DIR / md_filename)
            md_filenames.append(md_filename)

        return md_filenames


_pdf_conversion_service: Optional[PdfConversionService] = None


def get_pdf_conversion_service() -> PdfConversionService:
    """Возвращает singleton PdfConversionService."""
    global _pdf_conversion_service
    if _pdf_conversion_service is None:
        _pdf_conversion_service = PdfConversionService()
    return _pdf_conversion_service
