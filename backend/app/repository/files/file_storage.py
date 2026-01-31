"""Хранилище для чтения и записи JSON файлов.

Модуль содержит класс FileStorage для работы с orjson: чтение и запись
JSON файлов. Поддерживает bonds.json, маппинги и coupons_data.json
с обработкой отсутствующего/поврежденного файла и очисткой UTF-8.
"""

from pathlib import Path
from typing import Any, Dict

import orjson

from app.utils.coupon_utils import clean_string_value


class FileStorage:
    """Хранилище для чтения и записи JSON файлов.

    Обеспечивает единообразную работу с orjson для чтения и записи
    JSON файлов (bonds.json, маппинги). Для coupons_data.json —
    обработка отсутствующего/поврежденного файла и очистка UTF-8 при записи.
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

    def read_coupons(self, path: Path) -> Dict[str, Any]:
        """Читает данные о купонах из JSON файла.

        При отсутствии файла или поврежденных данных возвращает {"bonds": {}}.

        Args:
            path: Путь к файлу coupons_data.json.

        Returns:
            Словарь с ключом "bonds". При ошибке — {"bonds": {}}.
        """
        if not path.exists():
            return {"bonds": {}}
        try:
            with open(path, "rb") as f:
                return orjson.loads(f.read())
        except (orjson.JSONDecodeError, UnicodeDecodeError) as exc:
            print(
                f"[КУПОНЫ] ВНИМАНИЕ: Файл {path} поврежден "
                f"(ошибка: {type(exc).__name__}: {exc})"
            )
            print("[КУПОНЫ] Файл будет пересоздан при следующем обновлении данных")
            return {"bonds": {}}

    def write_coupons(self, path: Path, data: Dict[str, Any]) -> None:
        """Записывает данные о купонах в JSON файл.

        Перед записью очищает строки для валидного UTF-8.
        При ошибке сериализации выполняет дополнительную очистку и повтор.

        Args:
            path: Путь к файлу coupons_data.json.
            data: Данные для сохранения.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        cleaned = clean_string_value(data)
        try:
            serialized = orjson.dumps(
                cleaned,
                option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
            )
            path.write_bytes(serialized)
        except (TypeError, ValueError) as exc:
            print(f"[КУПОНЫ] ВНИМАНИЕ: Ошибка при сериализации данных: {exc}")
            print("[КУПОНЫ] Попытка дополнительной очистки данных...")
            cleaned = clean_string_value(cleaned)
            serialized = orjson.dumps(
                cleaned,
                option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
            )
            path.write_bytes(serialized)

    def ensure_coupons_exists(self, path: Path) -> None:
        """Создает файл coupons_data.json с начальной структурой, если его нет.

        Args:
            path: Путь к файлу coupons_data.json.
        """
        if not path.exists():
            self.write_coupons(path, {"bonds": {}})
