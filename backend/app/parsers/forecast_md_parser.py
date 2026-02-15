"""Парсер среднесрочного прогноза Банка России из Markdown.

Читает содержимое .md файла (формат forecast_251024.md), извлекает дату заседания,
таблицы «Основные параметры прогноза» и «Показатели платёжного баланса» и возвращает
структурированные данные для сохранения в БД. Не выполняет I/O — принимает строку.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ——— Вспомогательные функции парсинга ———


def _parse_date_from_header(content: str) -> str:
    """Извлекает дату заседания из заголовка. Формат: «24 октября 2025 года» -> YYYY-MM-DD."""
    months = {
        "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
        "мая": "05", "июня": "06", "июля": "07", "августа": "08",
        "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12",
    }
    pattern = r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})\s+года"
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        day = match.group(1).zfill(2)
        month = months[match.group(2).lower()]
        year = match.group(3)
        return f"{year}-{month}-{day}"
    raise ValueError("Не удалось извлечь дату заседания из заголовка")


def _parse_value(value_str: str) -> Optional[Dict[str, float]]:
    """Парсит значение: одиночное число или диапазон мин–макс. Прочерк -> None."""
    if not value_str or value_str.strip() == "-":
        return None
    value_str = value_str.strip().replace(",", ".")
    value_str = re.sub(r"\((-?\d+\.?\d*)\)", r"\1", value_str)
    range_match = re.search(r"(-?\d+\.?\d*)\s*[–-]\s*(-?\d+\.?\d*)", value_str)
    if range_match:
        return {"мин": float(range_match.group(1)), "макс": float(range_match.group(2))}
    try:
        num = float(value_str)
        return {"мин": num, "макс": num}
    except ValueError:
        return None


def _parse_single_value(value_str: str) -> Optional[float]:
    """Парсит одиночное число для платёжного баланса."""
    if not value_str or value_str.strip() == "-":
        return None
    value_str = value_str.strip().replace(",", ".")
    try:
        return float(value_str)
    except ValueError:
        return None


def _extract_year_from_header(cell: str) -> Optional[int]:
    """Извлекает год из ячейки заголовка, игнорируя подпись в скобках (факт/оценка), (факт) и т.п.

    Примеры: "2025 (факт/оценка)" -> 2025, "  2024 (факт) " -> 2024, "2026" -> 2026.
    """
    if not cell or not cell.strip():
        return None
    m = re.search(r"\b(20\d{2})\b", cell.strip())
    return int(m.group(1)) if m else None


def _find_table_section(content: str, section_title: str) -> Optional[str]:
    """Находит секцию таблицы по заголовку и возвращает её текст (строки с |)."""
    lines = content.split("\n")
    start_idx = None
    for i, line in enumerate(lines):
        if section_title.lower() in line.lower():
            for j in range(i + 1, min(i + 10, len(lines))):
                if "|" in lines[j] and "---" not in lines[j]:
                    start_idx = j
                    break
            if start_idx is not None:
                break
    if start_idx is None:
        return None
    table_lines = []
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if line.startswith("##"):
            break
        if "|" in line:
            table_lines.append(line)
    return "\n".join(table_lines)


# Маппинг: (паттерн в таблице, ключ для данных, человекочитаемое название)
_MAIN_INDICATOR_MAPPING = [
    ("Инфляция, в %, декабрь к декабрю предыдущего года", "инфляция_декабрь_к_декабрю", "Инфляция, декабрь к декабрю предыдущего года, %"),
    ("Инфляция, в среднем за год, в %к предыдущему году", "инфляция_среднегодовая", "Инфляция, в среднем за год, %"),
    ("Ключевая ставка, в среднем за год, в %годовых", "ключевая_ставка_средняя", "Ключевая ставка, в среднем за год, % годовых"),
    ("Валовой внутренний продукт", "ввп", "Валовой внутренний продукт, прирост в % к предыдущему году"),
    ("- в %, IV квартал к IV кварталу предыдущего года", "ввп_q4_q4", "ВВП, IV квартал к IV кварталу предыдущего года, %"),
    ("Расходы на конечное потребление", "расходы_конечного_потребления", "Расходы на конечное потребление, прирост в % к предыдущему году"),
    ("- домашних хозяйств", "расходы_домохозяйств", "Расходы домашних хозяйств, прирост в % к предыдущему году"),
    ("Валовое накопление", "валовое_накопление", "Валовое накопление, прирост в % к предыдущему году"),
    ("- основного капитала", "накопление_основного_капитала", "Накопление основного капитала, прирост в % к предыдущему году"),
    ("Экспорт", "экспорт", "Экспорт, прирост в % к предыдущему году"),
    ("Импорт", "импорт", "Импорт, прирост в % к предыдущему году"),
    ("Денежная масса в национальном определении", "денежная_масса", "Денежная масса в национальном определении, прирост в % к предыдущему году"),
    ("Требования банковской системы к экономике в рублях и иностранной валюте", "требования_к_экономике", "Требования банковской системы к экономике, прирост в % к предыдущему году"),
    ("- к организациям", "требования_к_организациям", "Требования к организациям, прирост в % к предыдущему году"),
    ("- к населению, в том числе", "требования_к_населению", "Требования к населению, прирост в % к предыдущему году"),
    ("ипотечные жилищные кредиты", "ипотечные_кредиты", "Ипотечные жилищные кредиты, прирост в % к предыдущему году"),
]

_BALANCE_PATTERNS = [
    ("Сальдо счета текущих операций и счета операций с капиталом", "счёт_текущих_операций", "Сальдо счета текущих операций и счета операций с капиталом, млрд долл. США"),
    ("Счет текущих операций", "счёт_текущих_операций", "Счёт текущих операций, млрд долл. США"),
    ("Торговый баланс", "торговый_баланс", "Торговый баланс, млрд долл. США"),
    ("Баланс услуг", "баланс_услуг", "Баланс услуг, млрд долл. США"),
    ("Баланс первичных и вторичных доходов", "баланс_доходов", "Баланс первичных и вторичных доходов, млрд долл. США"),
    ("Сальдо финансового счета, исключая резервные активы", "финансовый_счёт", "Сальдо финансового счета, исключая резервные активы, млрд долл. США"),
    ("Чистое принятие обязательств", "принятие_обязательств", "Чистое принятие обязательств, млрд долл. США"),
    ("Чистое приобретение финансовых активов", "приобретение_финансовых_активов", "Чистое приобретение финансовых активов, исключая резервные активы, млрд долл. США"),
    ("Чистые ошибки и пропуски", "ошибки_и_пропуски", "Чистые ошибки и пропуски, млрд долл. США"),
    ("Изменение резервных активов", "изменение_резервов", "Изменение резервных активов, млрд долл. США"),
    ("Цена нефти", "цена_нефти", "Цена нефти для налогообложения, в среднем за год, долл. США за баррель"),
]


def _parse_table_header_years(header_line: str) -> tuple[List[int], List[int]]:
    """Разбирает строку заголовка таблицы по ячейкам и возвращает (годы в порядке столбцов, индексы столбцов с годами).

    По разным отчётам годы и число столбцов разные. Заголовок и строки данных парсятся с фильтром if p.strip(),
    поэтому в заголовке остаются только ячейки с годами (индексы 0,1,2,...), а в строке данных — название
    показателя (индекс 0) и значения (индексы 1,2,...). Значение для years[i] в строке данных лежит в
    parts[column_indices[i] + 1].
    """
    header_parts = [p.strip() for p in header_line.split("|") if p.strip()]
    years: List[int] = []
    column_indices: List[int] = []
    for i, part in enumerate(header_parts):
        y = _extract_year_from_header(part)
        if y is not None:
            years.append(y)
            column_indices.append(i)
    return years, column_indices


def _parse_main_indicators_table(table_content: str) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Парсит таблицу «Основные параметры прогноза». Возвращает (список по годам, names key->title)."""
    lines = [line.strip() for line in table_content.split("\n") if line.strip() and "|" in line]
    if not lines:
        return [], {}

    years, col_indices = _parse_table_header_years(lines[0])
    if not years or not col_indices:
        return [], {}

    result = {y: {} for y in years}
    names_mapping = {}

    for line in lines[1:]:
        if "---" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        indicator_name = parts[0]
        json_key = None
        russian_name = None
        for pattern, key, russian in _MAIN_INDICATOR_MAPPING:
            if pattern in indicator_name:
                json_key, russian_name = key, russian
                names_mapping[key] = russian
                break
        if not json_key:
            continue
        for i, year in enumerate(years):
            # В строке данных индекс 0 — название показателя, значения по годам — с индекса 1
            value_idx = col_indices[i] + 1
            if value_idx < len(parts):
                v = _parse_value(parts[value_idx])
                if v:
                    result[year][json_key] = v

    out = []
    for year in sorted(years):
        row = {"год": year, **result[year]}
        out.append(row)
    return out, names_mapping


def _parse_balance_table(table_content: str) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Парсит таблицу «Показатели платёжного баланса». Возвращает (список по годам, names key->title).

    Разбор по столбцам: годы и индексы столбцов берутся из заголовка, в строках данных
    значения читаются по тем же индексам (в разных отчётах набор годов разный).
    """
    lines = [line.strip() for line in table_content.split("\n") if line.strip() and "|" in line]
    if not lines:
        return [], {}

    years, col_indices = _parse_table_header_years(lines[0])
    if not years or not col_indices:
        return [], {}

    result = {y: {} for y in years}
    names_mapping = {}
    export_count = import_count = 0

    for line in lines[1:]:
        if "---" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        indicator_name = parts[0]
        json_key = None
        if indicator_name.strip() == "Экспорт":
            export_count += 1
            json_key = "товарный_экспорт" if export_count == 1 else "экспорт_услуг"
            names_mapping[json_key] = "Товарный экспорт, млрд долл. США" if export_count == 1 else "Экспорт услуг, млрд долл. США"
        elif indicator_name.strip() == "Импорт":
            import_count += 1
            json_key = "товарный_импорт" if import_count == 1 else "импорт_услуг"
            names_mapping[json_key] = "Товарный импорт, млрд долл. США" if import_count == 1 else "Импорт услуг, млрд долл. США"
        else:
            for pattern, key, russian in _BALANCE_PATTERNS:
                if pattern in indicator_name:
                    json_key, names_mapping[key] = key, russian
                    break
        if not json_key:
            continue
        for i, year in enumerate(years):
            # В строке данных индекс 0 — название показателя, значения по годам — с индекса 1
            value_idx = col_indices[i] + 1
            if value_idx < len(parts):
                val = _parse_single_value(parts[value_idx])
                if val is not None:
                    result[year][json_key] = val

    out = []
    for year in sorted(years):
        out.append({"год": year, **result[year]})
    return out, names_mapping


# ——— Публичный API ———


@dataclass
class ParsedForecast:
    """Результат парсинга одного .md файла прогноза.

    - forecast_date / meeting_date / publication_date: YYYY-MM-DD (из заголовка).
    - names_main, names_balance: ключ показателя -> человекочитаемое название.
    - main_indicators: список dict с ключом «год» и ключами показателей -> {«мин», «макс»}.
    - balance: список dict с ключом «год» и ключами показателей -> float.
    """
    forecast_date: str
    meeting_date: str
    publication_date: str
    names_main: Dict[str, str] = field(default_factory=dict)
    names_balance: Dict[str, str] = field(default_factory=dict)
    main_indicators: List[Dict[str, Any]] = field(default_factory=list)
    balance: List[Dict[str, Any]] = field(default_factory=list)


def parse_forecast_content(content: str) -> ParsedForecast:
    """Парсит содержимое Markdown-файла прогноза Банка России.

    Args:
        content: Текст .md файла (например, как в forecast_251024.md).

    Returns:
        ParsedForecast с датами, названиями показателей и данными по годам.

    Raises:
        ValueError: Если не найдена дата заседания или одна из таблиц.
    """
    date_meeting = _parse_date_from_header(content)
    main_section = _find_table_section(content, "Основные параметры прогноза")
    if not main_section:
        raise ValueError("Не найдена таблица «Основные параметры прогноза»")
    balance_section = _find_table_section(content, "Показатели платежного баланса")
    if not balance_section:
        raise ValueError("Не найдена таблица «Показатели платёжного баланса»")

    main_rows, names_main = _parse_main_indicators_table(main_section)
    balance_rows, names_balance = _parse_balance_table(balance_section)

    return ParsedForecast(
        forecast_date=date_meeting,
        meeting_date=date_meeting,
        publication_date=date_meeting,
        names_main=names_main,
        names_balance=names_balance,
        main_indicators=main_rows,
        balance=balance_rows,
    )
