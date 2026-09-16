"""Модуль парсинга Excel-файлов Росстата с индексами потребительских цен (ИПЦ).

Извлекает показатели для Российской Федерации (код территории 643):
- ипц
- продовольстенные товары
- непродовольственные товары
- услуги

По всем вкладкам месяцев по порядку, исключая вкладки содержания.
"""

import logging
from datetime import date
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


class IpcExcelParser:
    """Парсер Excel-таблиц индексов потребительских цен Росстата."""

    # Ключевые слова для исключения вкладок содержания
    CONTENT_SHEET_KEYWORDS: Tuple[str, ...] = (
        "содержан",
        "оглавлен",
        "contents",
        "content",
        "toc",
    )

    # Регулярное выражение для извлечения месяца и года из имени вкладки
    # Примеры: "08 (2026)", "01 (2024)", "январь (2024)", "февраль (2026)"
    SHEET_NAME_REGEX = re.compile(
        r"^(?P<month>.*?)\s*[\(\[]\s*(?P<year>\d{4})\s*[\)\]]",
        re.IGNORECASE,
    )

    # Маппинг названий месяцев в двухзначный номер месяца
    MONTH_NAME_TO_NUMBER: Dict[str, str] = {
        "январь": "01",
        "января": "01",
        "янв": "01",
        "февраль": "02",
        "февраля": "02",
        "фев": "02",
        "март": "03",
        "марта": "03",
        "мар": "03",
        "апрель": "04",
        "апреля": "04",
        "апр": "04",
        "май": "05",
        "мая": "05",
        "июнь": "06",
        "июня": "06",
        "июн": "06",
        "июль": "07",
        "июля": "07",
        "июл": "07",
        "август": "08",
        "августа": "08",
        "авг": "08",
        "сентябрь": "09",
        "сентября": "09",
        "сен": "09",
        "октябрь": "10",
        "октября": "10",
        "окт": "10",
        "ноябрь": "11",
        "ноября": "11",
        "ноя": "11",
        "декабрь": "12",
        "декабря": "12",
        "дек": "12",
    }

    def parse_file(self, file_path: Union[str, Path]) -> list[Dict[str, str]]:
        """Парсит Excel-файл и возвращает структурированный словарь данных ИПЦ.

        Формат результата:
        {
            "год": {
                "месяц": {
                    "ипц": "...",
                    "продовольстенные товары": "...",
                    "непродовольственные товары": "...",
                    "услуги": "..."
                }
            }
        }

        Args:
            file_path: Путь к файлу .xlsx.

        Returns:
            Словарь данных ИПЦ по годам и месяцам в порядке обхода вкладок.

        Raises:
            FileNotFoundError: Если файл не существует.
            ValueError: Если не удалось прочитать ни одной валидной вкладки.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Excel-файл не найден: {path}")

        logger.info("[IPC PARSER] Открытие книги Excel: %s", path)
        wb = openpyxl.load_workbook(filename=str(path), data_only=True, read_only=False)

        result: list[Dict[str, str]] = []
        total_sheets_processed = 0

        try:
            for sheet_name in wb.sheetnames:
                if self._is_content_sheet(sheet_name):
                    logger.info("[IPC PARSER] Пропуск вкладки содержания: '%s'", sheet_name)
                    continue

                record_data = self._parse_sheet_name(sheet_name)
                if not record_data:
                    logger.warning(
                        "[IPC PARSER] Пропуск вкладки с неизвестным форматом имени: '%s'",
                        sheet_name,
                    )
                    continue

                #month_name, year_str = parsed_sheet_info
                ws: Worksheet = wb[sheet_name]

                data = self._extract_indicators_for_code_643(ws, sheet_name)
                if data is None:
                    logger.warning(
                        "[IPC PARSER] Не удалось извлечь данные территории 643 на вкладке '%s'",
                        sheet_name,
                    )
                    continue

                data["record_data"] = record_data.isoformat()

                result.append(data)

        finally:
            wb.close()

        if not result:
            logger.warning("[IPC PARSER] Не извлечено ни одной записи из файла %s", path)

        logger.info(
            "[IPC PARSER] Завершён парсинг файла %s: обработано месяцев: %d, годов: %d",
            path.name,
            total_sheets_processed,
            len(result),
        )
        return result

    def _is_content_sheet(self, sheet_name: str) -> bool:
        """Проверяет, является ли вкладка оглавлением/содержанием."""
        name_lower = sheet_name.strip().lower()
        return any(kw in name_lower for kw in self.CONTENT_SHEET_KEYWORDS)

    def _normalize_month_two_digits(self, month_raw: str) -> str:
        """Нормализует месяц к двузначной строке '01' - '12'.

        Поддерживает:
        - Двузначные или однозначные числа ('08', '8' -> '08')
        - Названия месяцев ('август', 'августа' -> '08')
        """
        clean = month_raw.strip().lower()
        if clean.isdigit():
            return f"{int(clean):02d}"

        if clean in self.MONTH_NAME_TO_NUMBER:
            return self.MONTH_NAME_TO_NUMBER[clean]

        for name, num in self.MONTH_NAME_TO_NUMBER.items():
            if clean.startswith(name) or name.startswith(clean):
                return num

        return clean.zfill(2)

    def _parse_sheet_name(self, sheet_name: str):
        """Извлекает месяц (в виде двузначного числа '01'-'12') и год из названия вкладки.

        Returns:
            Кортеж (месяц_двузначным_числом, год_строка) или None.
        """
        stripped = sheet_name.strip()
        match = self.SHEET_NAME_REGEX.search(stripped)
        if match:
            month_raw = match.group("month").strip()
            year = match.group("year").strip()
            if month_raw and year:
                month = self._normalize_month_two_digits(month_raw)
                return date(int(year), int(month), 1)

        # Запасной вариант: поиск 4 цифр года в названии вкладки
        year_match = re.search(r"(\d{4})", stripped)
        if year_match:
            year = year_match.group(1)
            # Месяц — оставшаяся часть строки без года и скобок
            month_raw = re.sub(r"[\(\)\[\]\d]", "", stripped).strip()
            if month_raw:
                month = self._normalize_month_two_digits(month_raw)
                return date(int(year), int(month), 1)

        return None

    def _get_cell_value(self, ws: Worksheet, row: int, col: int) -> Any:
        """Возвращает значение ячейки с учётом объединённых ячеек (merged cells)."""
        cell = ws.cell(row=row, column=col)
        val = cell.value
        if val is not None:
            return val

        # Если ячейка объединена, значение лежит в левой верхней ячейке диапазона
        for merged_range in ws.merged_cells.ranges:
            if (
                merged_range.min_row <= row <= merged_range.max_row
                and merged_range.min_col <= col <= merged_range.max_col
            ):
                return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value

        return None

    def _find_row_and_col_code_643(self, ws: Worksheet) -> Optional[Tuple[int, int]]:
        """Ищет строку, соответствующую коду территории 643 (Российская Федерация).

        Returns:
            Кортеж (номер_строки, номер_колонки_с_кодом) или None.
        """
        max_search_row = min(ws.max_row, 100)
        max_search_col = min(ws.max_column, 15)

        # 1. Поиск по числовому или строковому коду 643
        for r in range(1, max_search_row + 1):
            for c in range(1, max_search_col + 1):
                val = self._get_cell_value(ws, r, c)
                if val is None:
                    continue

                if isinstance(val, (int, float)):
                    if int(val) == 643:
                        return r, c

                str_val = str(val).strip()
                if str_val in ("643", "0643"):
                    return r, c
                # Обработка строковых представлений вида "643.0"
                if str_val.replace(".0", "") == "643":
                    return r, c

        # 2. Запасной поиск по тексту "Российская Федерация"
        for r in range(1, max_search_row + 1):
            for c in range(1, max_search_col + 1):
                val = self._get_cell_value(ws, r, c)
                if val is None:
                    continue
                str_val = str(val).strip().lower()
                if "российская федерация" in str_val or str_val == "рф":
                    # Колонку кода предполагаем слева от наименования или текущую
                    code_col = max(1, c - 1)
                    return r, code_col

        return None

    def _find_indicator_columns(
        self,
        ws: Worksheet,
        row_643: int,
        code_col: int,
    ) -> Dict[str, int]:
        """Определяет индексы колонок для 4 показателей на основе анализа шапки таблицы.

        Показатели:
        - ipc: ИПЦ (Все товары и услуги)
        - food: Продовольственные товары
        - non_food: Непродовольственные товары
        - services: Услуги
        """
        columns_found: Dict[str, int] = {}
        max_col = min(ws.max_column, 40)

        # Проверяем заголовки колонок в строках шапки таблицы
        for c in range(code_col + 1, max_col + 1):
            header_cells = [
                str(self._get_cell_value(ws, r, c)).strip().lower()
                for r in range(1, row_643)
                if self._get_cell_value(ws, r, c) is not None
            ]

            for h in header_cells:
                if h == "ипц" and "ipc" not in columns_found:
                    columns_found["ipc"] = c
                    break
                if h == "непродовольственные товары" and "non_food" not in columns_found:
                    columns_found["non_food"] = c
                    break
                if h == "продовольственные товары" and "food" not in columns_found:
                    columns_found["food"] = c
                    break
                if h == "услуги" and "services" not in columns_found:
                    columns_found["services"] = c
                    break

        # Если какая-то колонка не нашлась по точному равенству ячейки, проверяем подстроку
        if len(columns_found) < 4:
            for c in range(code_col + 1, max_col + 1):
                col_text = " ".join(
                    str(self._get_cell_value(ws, r, c)).strip().lower()
                    for r in range(1, row_643)
                    if self._get_cell_value(ws, r, c) is not None
                )
                if "непродовольственные товары" in col_text and "non_food" not in columns_found:
                    columns_found["non_food"] = c
                elif "продовольственные товары" in col_text and "food" not in columns_found:
                    columns_found["food"] = c
                elif "услуги" in col_text and "services" not in columns_found:
                    columns_found["services"] = c
                elif "ипц" in col_text and "ipc" not in columns_found:
                    columns_found["ipc"] = c

        # Позиционный fallback (в стандартной таблице колонки идут: ИПЦ -> Прод -> Непрод -> Услуги)
        base_col = code_col + 2
        columns_found.setdefault("ipc", base_col)
        columns_found.setdefault("food", base_col + 1)
        columns_found.setdefault("non_food", base_col + 2)
        columns_found.setdefault("services", base_col + 3)

        return columns_found

    def _extract_indicators_for_code_643(
        self,
        ws: Worksheet,
        sheet_name: str,
    ) -> Optional[Dict[str, str]]:
        """Извлекает 4 показателя для строки территории 643."""
        loc = self._find_row_and_col_code_643(ws)
        if not loc:
            logger.warning("[IPC PARSER] Вкладка '%s': код 643 не найден", sheet_name)
            return None

        row_643, code_col = loc
        cols = self._find_indicator_columns(ws, row_643, code_col)

        raw_ipc = self._get_cell_value(ws, row_643, cols["ipc"])
        raw_food = self._get_cell_value(ws, row_643, cols["food"])
        raw_non_food = self._get_cell_value(ws, row_643, cols["non_food"])
        raw_services = self._get_cell_value(ws, row_643, cols["services"])

        return {
            "ipc": self._format_cell_value(raw_ipc),
            "food_ipc": self._format_cell_value(raw_food),
            "non_food_ipc": self._format_cell_value(raw_non_food),
            "services_ipc": self._format_cell_value(raw_services),
        }

    @staticmethod
    def _format_cell_value(val: Any) -> str:
        """Преобразует значение ячейки в строковый формат для JSON."""
        if val is None:
            return ""

        if isinstance(val, (int, float)):
            # Округляем до 4 знаков для устранения погрешностей float представления
            val_rounded = round(float(val), 4)
            if val_rounded == int(val_rounded):
                return str(int(val_rounded))
            # Форматируем число без лишних хвостовых нулей
            formatted = f"{val_rounded:.4f}".rstrip("0").rstrip(".")
            return formatted

        s = str(val).strip()
        # Заменяем запятую на точку для чисел вида "100,15"
        if re.match(r"^\d+,\d+$", s):
            s = s.replace(",", ".")
        return s
