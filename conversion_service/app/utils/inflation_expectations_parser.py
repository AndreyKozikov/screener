"""Парсер Excel-файла с инфляционными ожиданиями.

Читает лист "Данные за все годы" и возвращает
{год: {месяц: {блок: {показатель: значение}}}}.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict

import openpyxl
from openpyxl.utils.datetime import from_excel

DEFAULT_EXCEL_PATH = Path(__file__).with_name("Infl_exp_26-08.xlsx")
DEFAULT_SHEET_NAME = "Данные за все годы"
DATE_ROW = 2
FIRST_DATA_COLUMN = 2

# Заголовок блока в колонке A и количество строк показателей под ним.
BLOCKS = (
    ("Прямые оценки годовой инфляции: медианные значения", 2),
    ("Прямые оценки пятилетней инфляции: медианные значения", 1),
    ("Индекс ожиданий", 1),
)

INDICATOR_KEYS = {
    "Прямые оценки годовой инфляции: медианные значения": {
        "наблюдаемая инфляция (в %)": "observed_annual_inflation",
        "ожидаемая инфляция (в %)": "expected_annual_inflation",
    },
    "Прямые оценки пятилетней инфляции: медианные значения": {
        "ожидаемая инфляция (в %)": "expected_five_year_inflation",
    },
    "Индекс ожиданий": {
        "индекс ожиданий  (в пунктах)": "expectations_index",
    },
}

JsonDict = Dict[str, Any]


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip().lower()


def _to_date(value: Any, epoch: datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return from_excel(value, epoch=epoch).date()
    if isinstance(value, str):
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    raise ValueError(f"Не удалось распознать дату: {value!r}")


def _json_value(value: Any) -> Any:
    """Приводит значение Excel к JSON-совместимому виду."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        number = text.replace(" ", "").replace(",", ".")
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", number):
            parsed = float(number)
            return int(parsed) if parsed.is_integer() else parsed

        return text

    return value


def parse_inflation_expectations_excel(
    excel_path: str | Path = DEFAULT_EXCEL_PATH,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> JsonDict:
    """Извлекает блоки инфляционных ожиданий из Excel-файла."""
    source_path = Path(excel_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Excel-файл не найден: {source_path}")

    workbook = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    try:
        if sheet_name not in workbook.sheetnames:
            raise ValueError(f"Лист {sheet_name!r} не найден")

        epoch = workbook.epoch
        rows = list(workbook[sheet_name].iter_rows(values_only=True))
    finally:
        workbook.close()

    if len(rows) < DATE_ROW:
        raise ValueError(f"В файле нет строки {DATE_ROW} с датами")

    dates: list[date] = []
    for value in rows[DATE_ROW - 1][FIRST_DATA_COLUMN - 1 :]:
        if value is None or (isinstance(value, str) and not value.strip()):
            break
        dates.append(_to_date(value, epoch))

    if not dates:
        raise ValueError(f"В строке {DATE_ROW} нет дат")

    labels = [_normalize(row[0] if row else None) for row in rows]

    result = {}

    for title, indicators_count in BLOCKS:
        target = _normalize(title)
        header_index = next((i for i, label in enumerate(labels) if target in label), None)
        if header_index is None:
            raise ValueError(f"Блок не найден в столбце A: {title!r}")

        block_rows = rows[header_index + 1: header_index + 1 + indicators_count]
        if len(block_rows) < indicators_count:
            raise ValueError(f"Недостаточно строк данных для блока {title!r}")

        for number, row in enumerate(block_rows, start=1):
            for index, period in enumerate(dates, start=FIRST_DATA_COLUMN - 1):
                value = row[index] if index < len(row) else None
                date_key = period.strftime("%Y-%m-%d")
                data = result.setdefault(date_key, {"recorddata": date_key})
                indicator = str(row[0] or f"Показатель {number}").strip()
                indicator_key = INDICATOR_KEYS[title].get(indicator, indicator)
                data[indicator_key] = _json_value(value)

    records = list(result.values())

    return records
