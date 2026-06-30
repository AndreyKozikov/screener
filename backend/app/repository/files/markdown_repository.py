"""Репозиторий для чтения Markdown-файлов из файловой системы.

Инкапсулирует операции чтения текстовых .md файлов из указанной директории.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict

logger: logging.Logger = logging.getLogger(__name__)


class MarkdownFileRepository:
    """Читает Markdown-файлы из указанной директории.

    Инкапсулирует файловые операции: проверку существования и чтение текста.
    Используется сервисным слоем для получения содержимого .md документов.
    """

    def __init__(self, base_dir: Path) -> None:
        """Инициализирует репозиторий с базовой директорией.

        Args:
            base_dir: Директория, в которой хранятся Markdown-файлы.
        """
        self._base_dir: Path = base_dir

    def read_files(
            self,
            filenames: List[str],
            base_dir: Optional[Path] = None,
    ) -> str:
        """Читает и объединяет содержимое Markdown-файлов.

        Каждый файл отделяется заголовком с именем файла. Файлы, которые
        не найдены или не удалось прочитать, пропускаются с логированием.

        Args:
            filenames: Список имён .md файлов в базовой директории.
            base_dir: Директория для поиска файлов. Если задана — используется
                вместо self._base_dir (например, подпапка по secid).

        Returns:
            Объединённый текст всех успешно прочитанных файлов.
        """
        dir_to_use: Path = base_dir if base_dir is not None else self._base_dir
        parts: List[str] = []
        for filename in filenames:
            file_path: Path = dir_to_use / filename
            if not file_path.is_file():
                logger.warning("Markdown-файл не найден, пропуск: %s", file_path)
                continue
            try:
                content: str = file_path.read_text(encoding="utf-8")
                parts.append(f"--- {filename} ---\n{content}")
            except OSError as exc:
                logger.error("Ошибка чтения файла %s: %s", file_path, exc)
        return "\n\n".join(parts)

    def read_emission_docs(
            self,
            secid: str,
            filename_excluded: tuple[str, ...],
            header_conditions: tuple[str, ...]
    ) -> List[Dict[str, str]]:

        bond_data_dir: Path = self._base_dir / secid
        if not bond_data_dir.exists():
            logger.warning("Директория не существует: %s", bond_data_dir)
            return []
        all_md_files: List[Path] = list(bond_data_dir.glob("*.md"))
        markdown_docs: List[Dict[str, str]] = []

        for md_path in all_md_files:
            # 1. Filter by filename (Pipeline 1 saves original_name.md)
            if self._filename_excluded_from_pipeline(md_path.name, filename_excluded):
                continue

            # 2. Filter by content headers
            try:
                md_content: str = md_path.read_text(encoding="utf-8")
                if not self._markdown_has_any_required_header(md_content, header_conditions):
                    continue
                markdown_docs.append({
                    "filename": md_path.name,
                    "content": md_content,
                })
            except OSError as exc:
                continue

        return markdown_docs

    @staticmethod
    def _filename_excluded_from_pipeline(
            filename: str,
            filename_excluded: tuple[str, ...]
    ) -> bool:

        """True, если имя файла содержит одну из исключающих фраз (проверка без учёта регистра)."""
        if not filename or not isinstance(filename, str):
            return False
        name_lower: str = filename.lower()
        return any(phrase.lower() in name_lower for phrase in filename_excluded)

    @staticmethod
    def _markdown_has_any_required_header(
            markdown: str,
            header_conditions: tuple[str, ...]
    ) -> bool:

        """True, если в тексте есть хотя бы один из требуемых заголовков (без учёта регистра)."""
        if not markdown or not markdown.strip():
            return False
        if not header_conditions:
            return True
        md_lower: str = markdown.lower()
        return any(header.lower() in md_lower for header in header_conditions)
