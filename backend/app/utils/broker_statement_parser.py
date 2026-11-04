"""Parse all supported sections of a broker HTML statement without database access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Any


class BrokerStatementParseError(ValueError):
    """The uploaded HTML is not a supported broker statement."""


@dataclass
class _Cell:
    text: str
    rowspan: int = 1
    colspan: int = 1


class _StatementHTMLReader(HTMLParser):
    """Read only top-level HTML tables; report markup is never executed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[_Cell]]] = []
        self._depth = 0
        self._table: list[list[_Cell]] = []
        self._row: list[_Cell] | None = None
        self._attrs: dict[str, str] | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._depth == 0:
                self._table = []
            self._depth += 1
            return
        if self._depth != 1:
            return
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._attrs = {key.lower(): value or "" for key, value in attrs}
            self._parts = []
        elif tag == "br" and self._attrs is not None:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._attrs is not None and self._row is not None:
            self._row.append(_Cell(
                text=" ".join("".join(self._parts).split()),
                rowspan=_positive_int(self._attrs.get("rowspan"), 1),
                colspan=_positive_int(self._attrs.get("colspan"), 1),
            ))
            self._attrs = None
            self._parts = []
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._depth:
            self._depth -= 1
            if self._depth == 0:
                self.tables.append(self._table)
                self._table = []

    def handle_data(self, data: str) -> None:
        if self._attrs is not None:
            self._parts.append(data)


def _positive_int(value: str | None, default: int) -> int:
    try:
        return max(1, int(value or default))
    except (TypeError, ValueError):
        return default


def _decode(content: bytes) -> str:
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("cp1251")
        except UnicodeDecodeError as exc:
            raise BrokerStatementParseError("Не удалось прочитать кодировку HTML-отчёта.") from exc


def _expand(rows: list[list[_Cell]]) -> list[list[str]]:
    grid: list[list[str | None]] = [[] for _ in rows]
    for row_index, cells in enumerate(rows):
        column = 0
        for cell in cells:
            while column < len(grid[row_index]) and grid[row_index][column] is not None:
                column += 1
            for target_row in range(row_index, min(len(rows), row_index + cell.rowspan)):
                width = column + cell.colspan
                grid[target_row].extend([None] * max(0, width - len(grid[target_row])))
                for target_column in range(column, width):
                    grid[target_row][target_column] = cell.text
            column += cell.colspan
    return [[cell or "" for cell in row] for row in grid]


def _header(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹¹⁰]", "", value)
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def _column(headers: list[str], *names: str, starts: bool = False) -> int | None:
    normalized = [_header(value) for value in headers]
    expected = [_header(value) for value in names]
    for index, value in enumerate(normalized):
        if value in expected or (starts and any(value.startswith(name) for name in expected)):
            return index
    return None


def _value(row: list[str], index: int | None) -> str:
    return row[index].strip() if index is not None and 0 <= index < len(row) else ""


def _decimal(value: str) -> Decimal | None:
    cleaned = value.replace("\u00a0", " ").replace("\u202f", " ").strip()
    if not cleaned or cleaned in {"-", "—", "–"}:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = re.sub(r"\s+", "", cleaned.strip("()"))
    cleaned = re.sub(r"[^0-9,.+\-]", "", cleaned)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        # In this report a comma is the decimal separator; remove any grouping dots.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        parsed = Decimal(cleaned)
        return -parsed if negative else parsed
    except InvalidOperation:
        raise ValueError(f"Некорректное числовое значение: {value}") from None


def _scaled(value: str, scale: int) -> int | None:
    number = _decimal(value)
    if number is None:
        return None
    return int((number * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _whole_quantity(value: str) -> int | None:
    number = _decimal(value)
    if number is None:
        return None
    if number != number.to_integral_value():
        raise ValueError(f"Количество облигаций должно быть целым числом: {value}")
    return int(number)


def _date(value: str) -> str | None:
    value = value.strip()
    if not value or value in {"-", "—", "–"}:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Некорректная дата: {value}")


def _currency(value: str) -> str | None:
    value = value.strip().upper()
    if not value:
        return None
    return {"РУБ": "RUB", "РУБ.": "RUB", "RUR": "RUB", "ДОЛЛАР США": "USD", "ЕВРО": "EUR"}.get(value, value)


def _raw(headers: list[str], row: list[str]) -> dict[str, str]:
    raw: dict[str, str] = {}
    seen: dict[str, int] = {}
    for index, header in enumerate(headers):
        key = header or f"column_{index + 1}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}__{seen[key]}"
        raw[key] = row[index].strip() if index < len(row) else ""
    return raw


def _row_is_data(row: list[str]) -> bool:
    values = [value.strip() for value in row if value.strip()]
    if not values:
        return False
    joined = " ".join(values).casefold()
    if joined.startswith("площадка:") or joined.startswith("итого") or joined.startswith("общий итог"):
        return False
    if all(re.fullmatch(r"\d+", value) for value in values):
        return False
    return True


def _parse_period(text: str) -> tuple[str, str]:
    plain = unescape(re.sub(r"<[^>]*>", " ", text))
    match = re.search(
        r"за\s+период\s+с\s+(\d{2}\.\d{2}\.\d{4})\s+по\s+(\d{2}\.\d{2}\.\d{4})",
        plain,
        flags=re.IGNORECASE,
    )
    if not match:
        raise BrokerStatementParseError("Не удалось определить отчётный период.")
    return _date(match.group(1)) or "", _date(match.group(2)) or ""


def _identify_table(rows: list[list[str]]) -> tuple[str, int] | None:
    for index, row in enumerate(rows):
        headers = [_header(cell) for cell in row]
        names = set(headers)
        if {"isin ценной бумаги", "эмитент", "вид категория тип иная информация"}.issubset(names) or (
            "isin ценной бумаги" in names and "эмитент" in names and "выпуск транш серия" in names
        ):
            return "securities", index
        if {"дата заключения", "дата расчетов", "наименование цб", "код цб", "вид", "количество шт", "номер сделки"}.issubset(names):
            return "trades", index
        if {"дата операции", "наименование цб", "код цб", "основание операции", "количество шт"}.issubset(names):
            return "security_movements", index
        if {"дата", "описание операции", "валюта", "сумма зачисления", "сумма списания"}.issubset(names):
            return "cash_operations", index
        if {"дата", "описание операции", "валюта", "сумма"}.issubset(names):
            return "income_payments", index
        if "isin ценной бумаги" in names and "наименование" in names and "количество шт" in names:
            if index > 0 and any("конец периода" in _header(cell) for cell in rows[index - 1]):
                return "positions", index
    return None


def _operation_type(description: str, fallback: str = "OTHER") -> str:
    text = description.casefold().replace("ё", "е")
    patterns = (
        ("комисси", "BROKER_FEE"), ("амортизац", "AMORTIZATION"),
        ("погашени", "REDEMPTION"), ("купон", "COUPON"), ("дивиденд", "DIVIDEND"),
        ("налог", "TAX"), ("пополнени", "DEPOSIT"), ("зачисление д/с", "DEPOSIT"),
        ("вывод", "WITHDRAWAL"), ("сделка", fallback),
    )
    for needle, kind in patterns:
        if needle in text:
            return kind
    return "OTHER"


def parse_broker_statement(content: bytes) -> dict[str, Any]:
    """Return normalized data and original rows from the broker HTML report."""
    if not content:
        raise BrokerStatementParseError("Файл отчёта пуст.")
    text = _decode(content)
    try:
        reader = _StatementHTMLReader()
        reader.feed(text)
        reader.close()
        start_date, end_date = _parse_period(text)
    except BrokerStatementParseError:
        raise
    except Exception as exc:
        raise BrokerStatementParseError("Не удалось прочитать HTML-отчёт брокера.") from exc

    tables: dict[str, tuple[list[list[str]], int]] = {}
    for raw_table in reader.tables:
        rows = _expand(raw_table)
        identified = _identify_table(rows)
        if identified:
            section, header_index = identified
            # Headers are semantic; duplicate tables of one section are combined below.
            tables.setdefault(section, ([], -1))
            if tables[section][1] == -1:
                tables[section] = (rows, header_index)
            else:
                tables[section][0].extend(rows[header_index + 1:])

    if not tables:
        raise BrokerStatementParseError("Не удалось определить структуру отчёта: поддерживаемые таблицы не найдены.")

    result: dict[str, Any] = {
        "report_period_start": start_date,
        "report_period_end": end_date,
        "securities": [], "trades": [], "cash_operations": [],
        "income_payments": [], "positions": [], "security_movements": [],
        "source_rows": [], "warnings": [],
    }
    sec_alias: dict[str, str] = {}

    def remember_source(section: str, row_number: int, raw: dict[str, str], status: str, error: str | None = None) -> None:
        result["source_rows"].append({
            "section_code": section,
            "source_row_number": row_number,
            "raw_data_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
            "parse_status": status,
            "parse_error": error,
        })

    for section, (rows, header_index) in tables.items():
        if header_index < 0:
            continue
        headers = rows[header_index]
        group = rows[header_index - 1] if header_index > 0 else []
        for offset, row in enumerate(rows[header_index + 1:], start=header_index + 2):
            if not _row_is_data(row):
                continue
            raw_headers = [
                f"{group[index]} / {header}" if section == "positions" and index < len(group) and group[index]
                else header
                for index, header in enumerate(headers)
            ]
            raw = _raw(raw_headers, row)
            try:
                if section == "securities":
                    code = _value(row, _column(headers, "код"))
                    isin = _value(row, _column(headers, "isin ценной бумаги")).upper().replace(" ", "") or None
                    name = _value(row, _column(headers, "наименование"))
                    if not (isin or code or name):
                        error = "В строке справочника отсутствуют ISIN, код и наименование ценной бумаги."
                        result["warnings"].append(f"{section}, строка {offset}: {error}")
                        remember_source(section, offset, raw, "error", error)
                        continue
                    name = name or code or isin
                    descriptor = _value(row, _column(headers, "вид категория тип иная информация"))
                    asset = "bond" if "облигац" in descriptor.casefold() else ("non_bond" if descriptor else "unknown")
                    record = {
                        "isin": isin, "security_code": code or None, "name": name or "Неизвестная ценная бумага",
                        "currency_code": None, "asset_type": asset, "security_category": descriptor or None,
                        "issuer": _value(row, _column(headers, "эмитент")) or None,
                        "raw_data_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
                    }
                    result["securities"].append(record)
                    key = isin or code or name
                    if key:
                        for alias in (isin, code, name):
                            if alias:
                                sec_alias[alias.casefold()] = key
                    remember_source(section, offset, raw, "parsed")
                    continue

                security_key: str | None = None
                if section in {"trades", "security_movements"}:
                    code = _value(row, _column(headers, "код цб"))
                    name = _value(row, _column(headers, "наименование цб"))
                    security_key = sec_alias.get(code.casefold()) or sec_alias.get(name.casefold()) or code or name or None

                if section == "trades":
                    trade_date = _date(_value(row, _column(headers, "дата заключения")))
                    quantity = _whole_quantity(_value(row, _column(headers, "количество шт")))
                    if not trade_date or quantity is None:
                        raise ValueError("Для сделки отсутствует дата или количество.")
                    source_kind = _value(row, _column(headers, "вид")).casefold()
                    operation = "BUY" if "покуп" in source_kind else "SELL" if "продаж" in source_kind else None
                    if operation is None:
                        raise ValueError("Не удалось определить вид сделки.")
                    security = next((s for s in result["securities"] if security_key and security_key in {
                        s.get("isin"), s.get("security_code"), s.get("name")}), None)
                    price = _decimal(_value(row, _column(headers, "цена")))
                    result["trades"].append({
                        "security_key": security_key,
                        "source_row_number": offset,
                        "trade_date": trade_date,
                        "settlement_date": _date(_value(row, _column(headers, "дата расчетов"))),
                        "trade_time": _value(row, _column(headers, "время заключения")) or None,
                        "operation_type": operation, "quantity": quantity,
                        "price_percent_scaled": int((price * 10_000).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if price is not None else None,
                        "amount_ex_nkd_minor": _scaled(_value(row, _column(headers, "сумма")), 100),
                        "nkd_minor": _scaled(_value(row, _column(headers, "нкд")), 100),
                        "broker_fee_minor": _scaled(_value(row, _column(headers, "комиссия брокера")), 100),
                        "exchange_fee_minor": _scaled(_value(row, _column(headers, "комиссия биржи")), 100),
                        "currency_code": _currency(_value(row, _column(headers, "валюта"))),
                        "trade_number": _value(row, _column(headers, "номер сделки")) or None,
                        "status": _value(row, _column(headers, "статус сделки")) or None,
                        "comment": _value(row, _column(headers, "комментарий")) or None,
                        "raw_data_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
                    })
                elif section == "cash_operations":
                    operation_date = _date(_value(row, _column(headers, "дата")))
                    if not operation_date:
                        raise ValueError("Для денежной операции отсутствует дата.")
                    credit = _scaled(_value(row, _column(headers, "сумма зачисления")), 100) or 0
                    debit = _scaled(_value(row, _column(headers, "сумма списания")), 100) or 0
                    description = _value(row, _column(headers, "описание операции"))
                    kind = _operation_type(description)
                    if "биржи" in description.casefold() or "комиссия биржи" in description.casefold():
                        kind = "EXCHANGE_FEE"
                    result["cash_operations"].append({
                        "security_key": None, "source_row_number": offset, "operation_date": operation_date, "operation_type": kind,
                        "description": description or None, "amount_minor": credit - debit,
                        "currency_code": _currency(_value(row, _column(headers, "валюта"))),
                        "raw_data_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
                    })
                elif section == "income_payments":
                    payment_date = _date(_value(row, _column(headers, "дата")))
                    amount = _scaled(_value(row, _column(headers, "сумма")), 100)
                    if not payment_date or amount is None:
                        raise ValueError("Для выплаты отсутствует дата или сумма.")
                    description = _value(row, _column(headers, "описание операции"))
                    income_text = description.casefold()
                    kind = next((candidate for needle, candidate in (
                        ("амортизац", "AMORTIZATION"), ("погашени", "REDEMPTION"),
                        ("купон", "COUPON"), ("дивиденд", "DIVIDEND"),
                    ) if needle in income_text), _operation_type(description))
                    result["income_payments"].append({
                        "security_key": None, "source_row_number": offset, "payment_date": payment_date, "income_type": kind,
                        "amount_minor": amount, "tax_withheld_minor": None, "net_amount_minor": amount,
                        "currency_code": _currency(_value(row, _column(headers, "валюта"))),
                        "description": description or None,
                        "raw_data_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
                    })
                elif section == "positions":
                    isin = _value(row, _column(headers, "isin ценной бумаги")).upper().replace(" ", "")
                    name = _value(row, _column(headers, "наименование"))
                    security_key = sec_alias.get(isin.casefold()) or isin or sec_alias.get(name.casefold()) or name or None
                    target = "конец периода"

                    def grouped_value(*fields: str, starts: bool = False) -> str:
                        for index, header in enumerate(headers):
                            if _header(header) in [_header(item) for item in fields] or (starts and any(_header(header).startswith(_header(item)) for item in fields)):
                                if index < len(group) and _header(group[index]) == target:
                                    return _value(row, index)
                        return ""

                    result["positions"].append({
                        "security_key": security_key, "snapshot_type": "CLOSING",
                        "quantity": _whole_quantity(grouped_value("количество шт")),
                        "market_value_ex_nkd_minor": _scaled(grouped_value("рыночная стоимость без нкд", starts=True), 100),
                    })
                elif section == "security_movements":
                    movement_date = _date(_value(row, _column(headers, "дата операции")))
                    if not movement_date:
                        raise ValueError("Для движения ценной бумаги отсутствует дата.")
                    description = " ".join(filter(None, (
                        _value(row, _column(headers, "вид")),
                        _value(row, _column(headers, "основание операции")),
                    )))
                    kind = _operation_type(description)
                    if kind == "OTHER" and description:
                        kind = "OTHER"
                        quantity = _whole_quantity(_value(row, _column(headers, "количество шт")))
                    if kind == "REDEMPTION" and quantity is not None:
                        quantity = -abs(quantity)
                    result["security_movements"].append({
                        "security_key": security_key, "source_row_number": offset, "movement_date": movement_date,
                        "movement_type": kind, "quantity_delta": quantity,
                        "nominal_amount_minor": None,
                        "currency_code": None, "description": description or None,
                        "raw_data_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
                    })
                remember_source(section, offset, raw, "parsed")
            except (ValueError, InvalidOperation) as exc:
                error = str(exc)
                result["warnings"].append(f"{section}, строка {offset}: {error}")
                remember_source(section, offset, raw, "error", error)

    aliases: dict[str, dict[str, Any]] = {}
    for security in result["securities"]:
        for alias in (security.get("isin"), security.get("security_code"), security.get("name")):
            if alias:
                aliases[alias.casefold()] = security
    unresolved_rows: set[tuple[str, int]] = set()
    for section, records in (
        ("trades", result["trades"]),
        ("positions", result["positions"]),
        ("security_movements", result["security_movements"]),
    ):
        for record in records:
            key = str(record.get("security_key") or "").casefold()
            if key and key in aliases:
                continue
            error = "Не удалось связать строку со справочником ценных бумаг по ISIN, коду или наименованию."
            source = next((item for item in result["source_rows"]
                           if item["section_code"] == section
                           and item["source_row_number"] == record["source_row_number"]), None)
            if source:
                source["parse_status"] = "error"
                source["parse_error"] = error
            source_key = (section, record["source_row_number"])
            if source_key not in unresolved_rows:
                result["warnings"].append(f"{section}, строка {record['source_row_number']}: {error}")
                unresolved_rows.add(source_key)
    for trade in result["trades"]:
        security = aliases.get(str(trade.get("security_key") or "").casefold())
        if not security or security.get("asset_type") != "bond":
            trade["price_percent_scaled"] = None
    for position in result["positions"]:
        security = aliases.get(str(position.get("security_key") or "").casefold())
        if security and position["snapshot_type"] == "CLOSING":
            security["currency_code"] = security.get("currency_code") or position.get("currency_code")
    return result


__all__ = ["BrokerStatementParseError", "parse_broker_statement"]
