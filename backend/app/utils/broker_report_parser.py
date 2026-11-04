"""Extract end-of-period bond holdings from a broker's HTML report."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Optional


class BrokerReportParseError(ValueError):
    """Raised when an uploaded file does not contain a supported holdings table."""


@dataclass(frozen=True)
class BrokerHolding:
    isin: str
    name: str
    quantity: int
    nominal: float
    market_value_without_accrued_interest: float

    @property
    def average_purchase_price(self) -> float:
        """Price as a percentage of nominal, based on the report valuation."""
        return (
            self.market_value_without_accrued_interest
            / self.quantity
            / self.nominal
            * 100
        )


@dataclass(frozen=True)
class ParsedBrokerReport:
    holdings: list[BrokerHolding]
    warnings: list[str]


@dataclass
class _Cell:
    text: str
    rowspan: int = 1
    colspan: int = 1


class _BrokerHtmlParser(HTMLParser):
    """Small, dependency-free HTML table reader; the report is never executed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[_Cell]]] = []
        self._table_depth = 0
        self._table: list[list[_Cell]] = []
        self._row: Optional[list[_Cell]] = None
        self._cell_attrs: Optional[dict[str, str]] = None
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._table_depth == 0:
                self._table = []
            self._table_depth += 1
            return
        if self._table_depth != 1:
            return
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_attrs = {key.lower(): (value or "") for key, value in attrs}
            self._cell_parts = []
        elif tag == "br" and self._cell_attrs is not None:
            self._cell_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell_attrs is not None and self._row is not None:
            attrs = self._cell_attrs
            self._row.append(
                _Cell(
                    text=" ".join("".join(self._cell_parts).split()),
                    rowspan=_positive_int(attrs.get("rowspan"), 1),
                    colspan=_positive_int(attrs.get("colspan"), 1),
                )
            )
            self._cell_attrs = None
            self._cell_parts = []
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth > 0:
            self._table_depth -= 1
            if self._table_depth == 0:
                self.tables.append(self._table)
                self._table = []

    def handle_data(self, data: str) -> None:
        if self._cell_attrs is not None:
            self._cell_parts.append(data)


def _positive_int(value: Optional[str], default: int) -> int:
    try:
        return max(1, int(value or default))
    except (TypeError, ValueError):
        return default


def _decode_report(content: bytes) -> str:
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1251", errors="replace")


def _expand_table(rows: list[list[_Cell]]) -> list[list[str]]:
    """Expand HTML row and column spans so every table column has an index."""
    grid: list[list[Optional[str]]] = [[] for _ in rows]
    for row_index, cells in enumerate(rows):
        column = 0
        for cell in cells:
            while column < len(grid[row_index]) and grid[row_index][column] is not None:
                column += 1
            for target_row in range(row_index, min(len(rows), row_index + cell.rowspan)):
                required_width = column + cell.colspan
                if len(grid[target_row]) < required_width:
                    grid[target_row].extend([None] * (required_width - len(grid[target_row])))
                for target_column in range(column, required_width):
                    grid[target_row][target_column] = cell.text
            column += cell.colspan
    return [[value or "" for value in row] for row in grid]


def _normalize_header(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹]", "", value)
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def _parse_number(value: str) -> Optional[float]:
    cleaned = value.replace("\xa0", " ").strip()
    if not cleaned or cleaned in {"-", "—", "–"}:
        return None
    cleaned = re.sub(r"\s+", "", cleaned).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if 0 <= index < len(row) else ""


def _holdings_columns(table: list[list[str]]) -> Optional[tuple[int, int, int, int, int, int]]:
    """Return (header row, ISIN, name, end quantity, end nominal, end value)."""
    # The report has a grouped header: one row names "Конец периода" and the
    # following row names the fields within that group.
    for header_index, row in enumerate(table):
        normalized = [_normalize_header(value) for value in row]
        isin_columns = [i for i, value in enumerate(normalized) if value == "isin ценной бумаги"]
        name_columns = [i for i, value in enumerate(normalized) if value == "наименование"]
        if not isin_columns or not name_columns or header_index == 0:
            continue

        group_row = [_normalize_header(value) for value in table[header_index - 1]]
        quantity_columns = [i for i, value in enumerate(normalized) if value in {"количество шт", "количество шт."}]
        nominal_columns = [i for i, value in enumerate(normalized) if value.startswith("номинал")]
        value_columns = [
            i for i, value in enumerate(normalized)
            if value.startswith("рыночная стоимость без нкд")
        ]
        for quantity_index in quantity_columns:
            if quantity_index >= len(group_row) or group_row[quantity_index] != "конец периода":
                continue
            nominal_index = next((i for i in nominal_columns if i < len(group_row) and group_row[i] == "конец периода"), None)
            value_index = next((i for i in value_columns if i < len(group_row) and group_row[i] == "конец периода"), None)
            if nominal_index is not None and value_index is not None:
                return header_index, isin_columns[0], name_columns[0], quantity_index, nominal_index, value_index
    return None


def parse_broker_report(content: bytes) -> ParsedBrokerReport:
    """Parse ISIN, end-of-period quantity, nominal and ex-accrued market value."""
    if not content:
        raise BrokerReportParseError("Файл отчёта пуст.")

    parser = _BrokerHtmlParser()
    try:
        parser.feed(_decode_report(content))
        parser.close()
    except Exception as exc:
        raise BrokerReportParseError("Не удалось прочитать HTML-отчёт брокера.") from exc

    selected: Optional[tuple[list[list[str]], tuple[int, int, int, int, int, int]]] = None
    for raw_table in parser.tables:
        expanded = _expand_table(raw_table)
        columns = _holdings_columns(expanded)
        if columns is not None:
            selected = (expanded, columns)
            break
    if selected is None:
        raise BrokerReportParseError(
            "В отчёте не найдена таблица ценных бумаг с колонками ISIN и «Конец периода»."
        )

    table, (header_index, isin_index, name_index, quantity_index, nominal_index, value_index) = selected
    aggregated: dict[str, dict[str, object]] = {}
    warnings: list[str] = []

    for row_number, row in enumerate(table[header_index + 1 :], start=header_index + 2):
        isin = _cell(row, isin_index).upper().replace(" ", "")
        name = _cell(row, name_index)
        if not isin or not re.fullmatch(r"[A-Z0-9]{8,20}", isin):
            continue

        quantity_value = _parse_number(_cell(row, quantity_index))
        nominal = _parse_number(_cell(row, nominal_index))
        market_value = _parse_number(_cell(row, value_index))
        if quantity_value is None or quantity_value <= 0:
            continue
        if not quantity_value.is_integer():
            warnings.append(f"Строка {row_number} ({isin}) пропущена: количество должно быть целым.")
            continue
        if nominal is None or nominal <= 0 or market_value is None or market_value <= 0:
            warnings.append(f"Строка {row_number} ({isin}) пропущена: нет номинала или рыночной стоимости на конец периода.")
            continue

        quantity = int(quantity_value)
        current = aggregated.get(isin)
        if current is None:
            aggregated[isin] = {
                "name": name or isin,
                "quantity": quantity,
                "nominal_value": quantity * nominal,
                "market_value": market_value,
            }
        else:
            current["quantity"] = int(current["quantity"]) + quantity
            current["nominal_value"] = float(current["nominal_value"]) + quantity * nominal
            current["market_value"] = float(current["market_value"]) + market_value

    holdings = [
        BrokerHolding(
            isin=isin,
            name=str(values["name"]),
            quantity=int(values["quantity"]),
            nominal=float(values["nominal_value"]) / int(values["quantity"]),
            market_value_without_accrued_interest=float(values["market_value"]),
        )
        for isin, values in aggregated.items()
    ]
    if not holdings:
        raise BrokerReportParseError(
            "В колонке «Конец периода» не найдено облигаций с положительным количеством и рыночной стоимостью без НКД."
        )
    return ParsedBrokerReport(holdings=holdings, warnings=warnings)
