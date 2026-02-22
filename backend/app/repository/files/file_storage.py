"""Хранилище для чтения и записи JSON файлов.

Модуль содержит класс FileStorage для работы с orjson: чтение и запись
JSON файлов (маппинги, columns.json и т.д.) с обработкой отсутствующего/
поврежденного файла и очисткой UTF-8. Также поддерживает удаление файлов
по шаблону расширения.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import orjson

from app.utils.coupon_utils import clean_string_value


class FileStorage:
    """Хранилище для чтения и записи JSON файлов.

    Обеспечивает единообразную работу с orjson для чтения и записи
    JSON файлов (маппинги, columns.json и т.д.) с очисткой UTF-8 при записи.
    """

    def read_json(self, path: Path) -> Any:
        """Читает JSON из файла по указанному пути.

        Args:
            path: Путь к JSON файлу.

        Returns:
            Распарсенное значение (dict, list и т.д.).

        Raises:
            OSError: Если не удалось прочитать файл.
            orjson.JSONDecodeError: Если содержимое не является валидным JSON.
        """
        with open(path, "rb") as f:
            return orjson.loads(f.read())

    def write_json(
        self,
        path: Path,
        data: Any,
        indent: bool = True,
        append_newline: bool = True,
    ) -> None:
        """Записывает данные в JSON файл по указанному пути.

        Args:
            path: Путь к файлу для записи.
            data: Данные для сериализации (dict, list и т.д.).
            indent: Если True, использовать отступы (OPT_INDENT_2).
            append_newline: Если True, добавить перевод строки в конец файла.

        Raises:
            OSError: Если не удалось записать файл.
        """
        options = 0
        if indent:
            options |= orjson.OPT_INDENT_2
        if append_newline:
            options |= orjson.OPT_APPEND_NEWLINE
        serialized = orjson.dumps(data, option=options)
        path.write_bytes(serialized)

    def save_binary_file(self, path: Path, content: bytes) -> None:
        """Записывает бинарные данные в файл.

        Args:
            path: Путь к файлу для записи.
            content: Бинарные данные.

        Raises:
            OSError: Если не удалось записать файл.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def save_text_file(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Записывает текстовые данные в файл.

        Args:
            path: Путь к файлу для записи.
            content: Текстовые данные.
            encoding: Кодировка файла (по умолчанию UTF-8).

        Raises:
            OSError: Если не удалось записать файл.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)

    def delete_files_by_pattern(
        self,
        directory: Path,
        extensions: Tuple[str, ...],
    ) -> None:
        """Удаляет все файлы из директории, соответствующие заданным расширениям.

        Операция выполняется по принципу best-effort: ошибки удаления отдельных
        файлов логируются, но не прерывают обработку остальных.

        Args:
            directory: Директория для поиска файлов.
            extensions: Кортеж glob-шаблонов расширений, например ("*.pdf", "*.md").
        """
        logger = logging.getLogger(__name__)
        for pattern in extensions:
            for file_path in directory.glob(pattern):
                try:
                    file_path.unlink()
                except OSError as exc:
                    logger.warning("Не удалось удалить файл %s: %s", file_path, exc)
