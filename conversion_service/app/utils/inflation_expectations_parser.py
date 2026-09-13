"""Парсер Excel-файла с инфляционными ожиданиями.

Читает лист "Данные за все годы", находит блоки показателей по заголовкам
в колонке A и сохраняет строки блоков в JSON вида:
{год: {месяц: {заголовок_блока: {показатель: значение}}}}.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import openpyxl
from openpyxl.utils.cell import get_column_letter
from openpyxl.utils.datetime import from_excel


DEFAULT_EXCEL_PATH = Path(__file__).with_name("Infl_exp_26-08.xlsx")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("inflation_expectations.json")
DEFAULT_SHEET_NAME = "Данные за все годы"
DATE_ROW = 2
LABEL_COLUMN = 1
FIRST_DATA_COLUMN = 2


@dataclass(frozen=True)
class IndicatorBlock:
    """Описание блока данных под заголовком в колонке A."""

    title: str
    data_rows_count: int


DEFAULT_INDICATOR_BLOCKS: tuple[IndicatorBlock, ...] = (
    IndicatorBlock("Прямые оценки годовой инфляции: медианные значения", 2),
    IndicatorBlock("Прямые оценки пятилетней инфляции: медианные значения", 1),
    IndicatorBlock("Индекс ожиданий", 1),
)

JsonDict = Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]


def normalize_text(value: Any) -> str:
    """Нормализует текст для устойчивого поиска заголовков."""
    if value is None:
        return ""

    text = str(value).replace("\xa0", " ").strip().lower()
    return re.sub(r"\s+", " ", text)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _trim_trailing_blank(values: Sequence[Any]) -> List[Any]:
    result = list(values)
    while result and _is_blank(result[-1]):
        result.pop()
    return result


def _coerce_date(value: Any, epoch: datetime, column_number: int) -> date:
    """Преобразует значение из строки дат Excel в date."""
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return from_excel(value, epoch=epoch).date()

    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

    column_letter = get_column_letter(column_number)
    raise ValueError(f"Не удалось распознать дату в ячейке {column_letter}{DATE_ROW}: {value!r}")


def _json_safe_value(value: Any) -> Any:
    """Готовит значение Excel к сериализации в JSON."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        normalized_number = text.replace(" ", "").replace(",", ".")
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", normalized_number):
            number = float(normalized_number)
            return int(number) if number.is_integer() else number

        return text

    return str(value)


def _extract_dates(ws: Any, epoch: datetime) -> List[date]:
    row_iter = ws.iter_rows(
        min_row=DATE_ROW,
        max_row=DATE_ROW,
        min_col=FIRST_DATA_COLUMN,
        values_only=True,
    )
    raw_row = next(row_iter, None)
    if raw_row is None:
        raise ValueError(f"Строка {DATE_ROW} с датами не найдена")

    raw_dates = _trim_trailing_blank(raw_row)
    if not raw_dates:
        raise ValueError(f"В строке {DATE_ROW} нет дат начиная со столбца B")

    dates: List[date] = []
    for offset, raw_value in enumerate(raw_dates, start=FIRST_DATA_COLUMN):
        if _is_blank(raw_value):
            column_letter = get_column_letter(offset)
            raise ValueError(f"Пустая дата внутри диапазона дат: {column_letter}{DATE_ROW}")
        dates.append(_coerce_date(raw_value, epoch=epoch, column_number=offset))

    return dates


def _find_indicator_data_rows(
    ws: Any,
    indicator_title: str,
    data_rows_count: int,
) -> List[Sequence[Any]]:
    target = normalize_text(indicator_title)
    if not target:
        raise ValueError("Текст заголовка показателя не может быть пустым")

    found_row_number: int | None = None
    data_rows: List[Sequence[Any]] = []

    for row_number, row in enumerate(ws.iter_rows(values_only=True), start=1):
        label = normalize_text(row[LABEL_COLUMN - 1] if row else None)

        if found_row_number is None:
            if target in label:
                found_row_number = row_number
            continue

        data_rows.append(row)
        if len(data_rows) == data_rows_count:
            break

    if found_row_number is None:
        raise ValueError(f"Заголовок показателя не найден в столбце A: {indicator_title!r}")

    if len(data_rows) < data_rows_count:
        raise ValueError(
            f"После строки {found_row_number} найдено только {len(data_rows)} "
            f"строк данных вместо {data_rows_count}"
        )

    return data_rows


def _cell_from_row(row: Sequence[Any], column_number: int) -> Any:
    index = column_number - 1
    return row[index] if index < len(row) else None


def _add_block_to_nested_dict(
    result: JsonDict,
    dates: Iterable[date],
    block_title: str,
    data_rows: Sequence[Sequence[Any]],
) -> None:
    periods = list(dates)

    for row_index, row in enumerate(data_rows, start=1):
        indicator_name = str(_cell_from_row(row, LABEL_COLUMN) or f"Показатель {row_index}").strip()

        for date_index, period_date in enumerate(periods):
            value_column = FIRST_DATA_COLUMN + date_index
            raw_value = _cell_from_row(row, value_column)

            year_key = str(period_date.year)
            month_key = f"{period_date.month:02d}"
            month_data = result.setdefault(year_key, {}).setdefault(month_key, {})
            block_data = month_data.setdefault(block_title, {})
            block_data[indicator_name] = _json_safe_value(raw_value)


def parse_inflation_expectations_excel(
    excel_path: str | Path = DEFAULT_EXCEL_PATH,
    sheet_name: str = DEFAULT_SHEET_NAME,
    indicator_blocks: Sequence[IndicatorBlock] = DEFAULT_INDICATOR_BLOCKS,
) -> JsonDict:
    """Извлекает блоки инфляционных ожиданий из Excel-файла."""
    source_path = Path(excel_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Excel-файл не найден: {source_path}")

    if not indicator_blocks:
        raise ValueError("Список блоков показателей не может быть пустым")

    workbook = openpyxl.load_workbook(
        filename=source_path,
        read_only=True,
        data_only=True,
    )

    try:
        if sheet_name not in workbook.sheetnames:
            available_sheets = ", ".join(workbook.sheetnames)
            raise ValueError(f"Лист {sheet_name!r} не найден. Доступные листы: {available_sheets}")

        worksheet = workbook[sheet_name]
        dates = _extract_dates(worksheet, epoch=workbook.epoch)
        result: JsonDict = {}

        for block in indicator_blocks:
            data_rows = _find_indicator_data_rows(
                worksheet,
                indicator_title=block.title,
                data_rows_count=block.data_rows_count,
            )
            _add_block_to_nested_dict(
                result=result,
                dates=dates,
                block_title=block.title,
                data_rows=data_rows,
            )

        return result
    finally:
        workbook.close()


def save_json(data: JsonDict, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Сохраняет словарь с данными в JSON-файл."""
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Парсинг Excel-файла с инфляционными ожиданиями в JSON",
    )
    parser.add_argument("--excel-path", default=str(DEFAULT_EXCEL_PATH), help="Путь к .xlsx файлу")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH), help="Путь к JSON файлу")
    parser.add_argument("--sheet-name", default=DEFAULT_SHEET_NAME, help="Название листа Excel")
    args = parser.parse_args()

    data = parse_inflation_expectations_excel(
        excel_path=args.excel_path,
        sheet_name=args.sheet_name,
    )
    output_path = save_json(data, args.output_path)
    print(f"JSON сохранён: {output_path}")


if __name__ == "__main__":
    main()
