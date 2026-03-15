"""Сервис конвертации документов в Markdown через внешний API.

Отправляет документы (PDF, DOC, DOCX, RTF) на внешний PDF2MD сервис. На конвертацию
не отправляются файлы, в имени которых (без учёта регистра) встречаются фразы:
«Отчетность МСФО», «Отчетность РСБУ», «Отчетность», «МСФО», «РСБУ», «Проспект»,
«Сертификат» — такие имена исключаются из списка до вызова API. Сохраняются только те markdown-файлы, в которых
есть хотя бы один из заголовков: «ДОКУМЕНТ, СОДЕРЖАЩИЙ УСЛОВИЯ РАЗМЕЩЕНИЯ ЦЕННЫХ БУМАГ»,
«РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ» или «Уведомление об итогах выпуска».
Файлы без ни одного из них отбрасываются и на диск не сохраняются.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.exceptions import PdfConversionConnectionError
from app.repository.files.file_storage import FileStorage
from app.utils.edisclosure_utils import clean_markdown_after_pdf2md
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

# Таймаут отключён (None): пайплайн всегда дожидается ответа сервиса конвертации.
_CONVERSION_TIMEOUT: Optional[float] = None

_HEADER_CONDITIONS: str = (
    "ДОКУМЕНТ, СОДЕРЖАЩИЙ УСЛОВИЯ РАЗМЕЩЕНИЯ ЦЕННЫХ БУМАГ"
)
_HEADER_DECISION: str = "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ"
_HEADER_NOTICE_ISSUE: str = "Уведомление об итогах выпуска"

# Фразы в имени файла (без учёта регистра), при наличии которых файл не отправляется на конвертацию.
_FILENAME_EXCLUDE_PHRASES: Tuple[str, ...] = (
    "Отчетность МСФО",
    "Отчетность РСБУ",
    "Отчетность",
    "МСФО",
    "РСБУ",
    "Проспект",
    "Сертификат",
)

# MIME-типы для поддерживаемых расширений документов.
_EXTENSION_MIME_MAP: Dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".rtf": "application/rtf",
}


def _filename_excluded_from_conversion(filename: str) -> bool:
    """True, если имя файла содержит одну из исключающих фраз (проверка без учёта регистра)."""
    if not filename or not isinstance(filename, str):
        return False
    name_lower: str = filename.lower()
    return any(phrase.lower() in name_lower for phrase in _FILENAME_EXCLUDE_PHRASES)


def _markdown_has_any_required_header(markdown: str) -> bool:
    """True, если в тексте есть хотя бы один из требуемых заголовков (без учёта регистра)."""
    if not markdown or not markdown.strip():
        return False
    md_lower: str = markdown.lower()
    return (
        _HEADER_CONDITIONS.lower() in md_lower
        or _HEADER_DECISION.lower() in md_lower
        or _HEADER_NOTICE_ISSUE.lower() in md_lower
    )


class PdfConversionService:
    """Конвертирует документы (PDF, DOC, DOCX, RTF) в Markdown через внешний PDF2MD API.

    Работает синхронно. Всегда использует batch-эндпоинт: передаёт один или
    несколько документов, результаты (.md) сохраняются через FileStorage.
    """

    def __init__(
        self,
        file_storage: Optional[FileStorage] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._file_storage: FileStorage = file_storage or FileStorage()
        self._base_url: str = (base_url or settings.PDF2MD_BASE_URL).rstrip("/")

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертирует документы (PDF, DOC, DOCX, RTF) из *data* и добавляет ключ ``md_filenames``.

        Args:
            data: Словарь, содержащий ключ ``doc_filenames`` со списком
                имён документов (PDF, DOC, DOCX или RTF). Если передан
                ``data_dir`` (Path или str), чтение файлов и запись .md
                выполняются в этой директории; иначе используется backend/app/data.

        Returns:
            Копия *data* с добавленным ключом ``md_filenames: List[str]``.
        """
        doc_filenames: List[str] = data.get("doc_filenames", [])

        if not doc_filenames:
            return {**data, "md_filenames": []}

        # Исключаем файлы по имени (отчётность, проспект, сертификат и т.д.) — проверка без учёта регистра.
        original_count: int = len(doc_filenames)
        doc_filenames = [
            f for f in doc_filenames
            if not _filename_excluded_from_conversion(f)
        ]
        excluded_count: int = original_count - len(doc_filenames)
        if excluded_count > 0:
            logger.info(
                "Исключено из конвертации по имени (отчётность, проспект, сертификат и т.д.): %d файл(ов)",
                excluded_count,
            )

        if not doc_filenames:
            return {**data, "md_filenames": []}

        data_dir: Any = data.get("data_dir")
        base_dir: Path = Path(data_dir) if data_dir is not None else _DATA_DIR
        if not isinstance(base_dir, Path):
            base_dir = Path(str(base_dir))

        md_filenames: List[str] = self._convert_batch(doc_filenames, base_dir)
        return {**data, "md_filenames": md_filenames}

    def _convert_batch(self, filenames: List[str], base_dir: Path) -> List[str]:
        """Конвертирует один или несколько документов (PDF, DOC, DOCX, RTF) через ``/api/v1/convert/batch``.

        Принимает список имён файлов (в т.ч. из одного элемента). Единая логика
        для любого количества документов. MIME-тип определяется по расширению файла.
        Файлы с расширением, отличным от .pdf, .docx, .doc, .rtf, пропускаются.

        Args:
            filenames: Имена документов (PDF, DOC, DOCX или RTF) в базовой директории.
            base_dir: Директория для чтения документов и записи .md.

        Returns:
            Список имён успешно созданных .md файлов.
        """
        files_payload: List[Tuple[str, Tuple[str, bytes, str]]] = []
        for filename in filenames:
            file_path: Path = base_dir / filename
            ext: str = file_path.suffix.lower()
            mime_type: Optional[str] = _EXTENSION_MIME_MAP.get(ext)
            if mime_type is None:
                logger.warning(
                    "Файл пропущен: расширение '%s' не поддерживается для конвертации: %s",
                    ext,
                    file_path,
                )
                continue
            if not file_path.is_file():
                logger.error("Файл не найден, пропуск: %s", file_path)
                continue
            files_payload.append(
                ("files", (filename, file_path.read_bytes(), mime_type)),
            )

        if not files_payload:
            return []

        url: str = f"{self._base_url}/api/v1/convert/batch"
        print(f"  [API] POST {url} (ожидание ответа без ограничения по времени)", flush=True)
        try:
            with httpx.Client(timeout=_CONVERSION_TIMEOUT) as client:
                response: httpx.Response = client.post(url, files=files_payload)
                response.raise_for_status()
                body: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            message: str = f"Ошибка batch-конвертации: {exc}"
            logger.error(message)
            raise PdfConversionConnectionError(message, cause=exc) from exc

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

            if not _markdown_has_any_required_header(markdown):
                logger.info(
                    "Пропуск сохранения %s: в тексте нет ни одного из заголовков "
                    "(ДОКУМЕНТ, СОДЕРЖАЩИЙ УСЛОВИЯ РАЗМЕЩЕНИЯ..., РЕШЕНИЕ О ВЫПУСКЕ... или Уведомление об итогах выпуска)",
                    original,
                )
                continue

            md_filename: str = Path(original).stem + ".md"
            markdown = clean_markdown_after_pdf2md(markdown)
            self._file_storage.save_text_file(base_dir / md_filename, markdown)
            logger.info("Сохранён markdown: %s", base_dir / md_filename)
            md_filenames.append(md_filename)

        return md_filenames


_pdf_conversion_service: Optional[PdfConversionService] = None


def get_pdf_conversion_service() -> PdfConversionService:
    """Возвращает singleton PdfConversionService."""
    global _pdf_conversion_service
    if _pdf_conversion_service is None:
        _pdf_conversion_service = PdfConversionService()
    return _pdf_conversion_service
