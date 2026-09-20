# -*- coding: utf-8 -*-

import argparse
import json
import logging
import re
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Any
import xml.etree.ElementTree as ET

import requests

try:
    from .rosstat_ipc_links_parser import fetch_weekly_ipc_links
except ImportError:
    from rosstat_ipc_links_parser import fetch_weekly_ipc_links

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SEC = 30
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}
_DEFAULT_OUTPUT_PATH = Path(__file__).with_name("rosstat_ipc_reports.json")
_DATE_RANGE_PATTERN = re.compile(
    r"\bс(?:о)?\s+(\d{1,2})\s+(?:([а-яА-ЯёЁ]+)\s+)?по\s+"
    r"(\d{1,2})\s+([а-яА-ЯёЁ]+)\s+(\d{4})\s+года?\b",
    re.IGNORECASE,
)
_DECIMAL_PATTERN = re.compile(r"\d{1,3}(?:[ ]\d{3})*(?:[,.]\d+)?")
_DECIMAL_PATTERN_TEXT = r"\d{1,3}(?:[ ]\d{3})*(?:[,.]\d+)?"
_PREVIOUS_DATE_REGISTRATION_MARKER = "предыдущейдатерегистрации"
_PROSE_DATE_PATTERN = (
    r"\d{1,2}(?:\s+[а-яё]+)?(?:\s+\d{4}\s*г(?:\.|ода)?)?"
)
_IPC_WEEKLY_PROSE_PATTERN = re.compile(
    rf"\bза\s+период\s+с(?:о)?\s+{_PROSE_DATE_PATTERN}\s+по\s+"
    rf"{_PROSE_DATE_PATTERN}\s+индекс\s+потребительских\s+цен\s*"
    rf"(?:\d+)?[^.]*?\bсоставил(?:а|о|и)?\s+({_DECIMAL_PATTERN_TEXT})\s*%",
    re.IGNORECASE,
)
_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(root: ET.Element, element_name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == element_name:
            return _normalise_text(" ".join(element.itertext()))
    return ""


def _normalise_text(value: str) -> str:
    return " ".join(
        value.replace("\xa0", " ")
        .replace("\u00ad", "")
        .replace("\u200b", "")
        .split()
    )


def _normalise_cell_text(cell: ET.Element) -> str:
    return _normalise_text(" ".join(cell.itertext()))


def _compact_text(value: str) -> str:
    value = value.lower().replace("ё", "е").replace("\u00ad", "")
    return re.sub(r"[^0-9a-zа-я]+", "", value)


def _is_previous_date_registration_header(value: str) -> bool:
    return _PREVIOUS_DATE_REGISTRATION_MARKER in _compact_text(value)


def _span_value(cell: ET.Element, attribute: str) -> int:
    try:
        value = int(cell.get(attribute, "1"))
    except (TypeError, ValueError):
        return 1
    return max(value, 1)


def _iter_table_rows(element: ET.Element):
    for child in list(element):
        child_name = _local_name(child.tag)
        if child_name == "table":
            continue
        if child_name == "tr":
            yield child
            continue
        yield from _iter_table_rows(child)


def _row_cells(row: ET.Element) -> List[ET.Element]:
    return [
        child
        for child in list(row)
        if _local_name(child.tag) in {"td", "th"}
    ]


def _expand_table_grid(table: ET.Element) -> List[List[str]]:
    # Rosstat reports are LibreOffice XHTML with frequent rowspan/colspan use.
    # Rebuild a logical grid before reading a value by column.
    grid: List[List[str]] = []
    rowspans = {}

    for row in _iter_table_rows(table):
        expanded_row = {}
        occupied_columns = set(rowspans)
        next_rowspans = {}

        for column_index, (text, rows_remaining) in rowspans.items():
            expanded_row[column_index] = text
            if rows_remaining > 1:
                next_rowspans[column_index] = (text, rows_remaining - 1)

        column_index = 0
        for cell in _row_cells(row):
            while column_index in occupied_columns:
                column_index += 1

            text = _normalise_cell_text(cell)
            colspan = _span_value(cell, "colspan")
            rowspan = _span_value(cell, "rowspan")

            for offset in range(colspan):
                target_column = column_index + offset
                expanded_row[target_column] = text
                occupied_columns.add(target_column)
                if rowspan > 1:
                    next_rowspans[target_column] = (text, rowspan - 1)

            column_index += colspan

        if expanded_row:
            max_column = max(expanded_row)
            grid.append([expanded_row.get(index, "") for index in range(max_column + 1)])

        rowspans = next_rowspans

    return grid


def _extract_decimal_value(value: str) -> Optional[str]:
    candidate = _normalise_text(value).replace("\u2212", "-")
    if _DECIMAL_PATTERN.fullmatch(candidate):
        return candidate.replace(" ", "")
    return None


def _extract_first_value_under_previous_date_column(grid: List[List[str]]) -> Optional[str]:
    for header_row_index, row in enumerate(grid):
        for column_index, cell in enumerate(row):
            if not _is_previous_date_registration_header(cell):
                continue

            for data_row in grid[header_row_index + 1 :]:
                if column_index >= len(data_row):
                    continue

                value = data_row[column_index]
                if _is_previous_date_registration_header(value):
                    continue

                decimal_value = _extract_decimal_value(value)
                if decimal_value is not None:
                    return decimal_value

    return None


def _extract_ipc_weekly_from_prose(root: ET.Element) -> Optional[str]:
    text = _normalise_text(" ".join(root.itertext()))
    match = _IPC_WEEKLY_PROSE_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).replace(" ", "")


def _parse_xml(html: str) -> ET.Element:
    return ET.fromstring(html.encode("utf-8"))


def _extract_date_range(root: ET.Element) -> tuple:
    title = _element_text(root, "title")
    if not title:
        title = _normalise_text(" ".join(root.itertext()))

    match = _DATE_RANGE_PATTERN.search(title)
    if match is None:
        raise ValueError("Не удалось найти период в заголовке отчёта")

    start_day = int(match.group(1))
    start_month_name = match.group(2) or match.group(4)
    end_day = int(match.group(3))
    end_month_name = match.group(4)
    end_year = int(match.group(5))
    start_month = _MONTHS.get(start_month_name.lower())
    end_month = _MONTHS.get(end_month_name.lower())
    if start_month is None:
        raise ValueError(f"Неизвестный месяц в заголовке отчёта: {start_month_name}")
    if end_month is None:
        raise ValueError(f"Неизвестный месяц в заголовке отчёта: {end_month_name}")

    start_year = end_year - 1 if start_month > end_month else end_year
    try:
        start = date(start_year, start_month, start_day)
        end = date(end_year, end_month, end_day)
    except ValueError as exc:
        raise ValueError("В заголовке отчёта указана некорректная дата") from exc

    return (
        f"{start.year}-{start.month:02d}-{start.day:02d}",
        f"{end.year}-{end.month:02d}-{end.day:02d}",
    )


def _extract_ipc_weekly(root: ET.Element) -> str:
    for table in root.iter():
        if _local_name(table.tag) != "table":
            continue

        value = _extract_first_value_under_previous_date_column(
            _expand_table_grid(table)
        )
        if value is not None:
            return value

    prose_value = _extract_ipc_weekly_from_prose(root)
    if prose_value is not None:
        return prose_value

    raise ValueError("Не удалось найти значение ИПЦ в столбце «К предыдущей дате регистрации»")



def parse_report(html: str, source_url: Optional[str] = None) -> Dict[str, Any]:
    root = _parse_xml(html)
    start_date, end_date = _extract_date_range(root)
    ipc_weekly = float(_extract_ipc_weekly(root).replace(",", "."))
    return {
        "source_url": source_url or "",
        "start_date": start_date,
        "end_date": end_date,
        "ipc_weekly": ipc_weekly
    }


def _fetch_report_html(
    url: str,
    *,
    verify_ssl: bool,
    timeout: int,
) -> str:
    with warnings.catch_warnings():
        if not verify_ssl:
            warnings.simplefilter("ignore")
        response = requests.get(
            url,
            headers=_DEFAULT_HEADERS,
            verify=verify_ssl,
            timeout=timeout,
        )
    response.encoding = "utf-8"
    response.raise_for_status()
    return response.text


def download_reports(
    compendium_url: str,
    verify_ssl: bool = False,
    timeout: int = _REQUEST_TIMEOUT_SEC,
) -> List[Dict[str, str]]:
    links = fetch_weekly_ipc_links(
        url=compendium_url,
        verify_ssl=verify_ssl,
        timeout=timeout,
    )
    reports: List[Dict[str, str]] = []
    for index, link in enumerate(links, start=1):

        try:
            html = _fetch_report_html(
                link,
                verify_ssl=verify_ssl,
                timeout=timeout,
            )
            report = parse_report(html, source_url=link)
        except Exception as exc:
            logger.error(
                "[ROSSTAT REPORT %d/%d] Ошибка обработки отчёта: %s; ошибка: %s",
                index,
                len(links),
                link,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Ошибка обработки отчёта {link}: {exc}") from exc

        reports.append(report)
    logger.info("Сохранено отчётов ИПЦ: %d", len(reports))
    return reports


def get_ipc_weekly(argv: Optional[List[str]] = None):

    try:
        payload = download_reports(
            compendium_url="https://rosstat.gov.ru/compendium/document/50798",
            verify_ssl=False,
            timeout=60,
        )
    except (OSError, ValueError, ET.ParseError, requests.RequestException, RuntimeError) as exc:
        logger.error("Не удалось загрузить отчёты ИПЦ: %s", exc)
        raise

    return payload

