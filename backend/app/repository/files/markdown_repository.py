"""Репозиторий для чтения Markdown-файлов из файловой системы.

Инкапсулирует операции чтения текстовых .md файлов из указанной директории.
"""

import logging
from pathlib import Path
from typing import List

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

    def read_files(self, filenames: List[str]) -> str:
        """Читает и объединяет содержимое Markdown-файлов.

        Каждый файл отделяется заголовком с именем файла. Файлы, которые
        не найдены или не удалось прочитать, пропускаются с логированием.

        Args:
            filenames: Список имён .md файлов в базовой директории.

        Returns:
            Объединённый текст всех успешно прочитанных файлов.
        """
        parts: List[str] = []
        for filename in filenames:
            file_path: Path = self._base_dir / filename
            if not file_path.is_file():
                logger.warning("Markdown-файл не найден, пропуск: %s", file_path)
                continue
            try:
                content: str = file_path.read_text(encoding="utf-8")
                parts.append(f"--- {filename} ---\n{content}")
            except OSError as exc:
                logger.error("Ошибка чтения файла %s: %s", file_path, exc)
        return "\n\n".join(parts)
