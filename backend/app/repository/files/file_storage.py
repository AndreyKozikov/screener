"""Хранилище для чтения и записи JSON файлов.

Модуль содержит класс FileStorage для работы с orjson: чтение и запись
JSON файлов (маппинги, columns.json и т.д.) с обработкой отсутствующего/
поврежденного файла и очисткой UTF-8.
"""

from pathlib import Path
from typing import Any, Dict

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
