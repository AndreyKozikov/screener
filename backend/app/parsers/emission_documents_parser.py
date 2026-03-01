"""Парсер таблицы эмиссионных документов с HTML-страницы e-disclosure.ru.

Извлекает данные из таблицы на странице
https://www.e-disclosure.ru/portal/files.aspx?id={id}&type=7.
Таблица ищется по пути #cont_wrap > div.spaceTbl > table.
Используется только стандартная библиотека (html.parser, re).
Результат — список словарей для таблицы БД emission_documents.
"""

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Union


def _normalize_header_cell(text: str) -> str:
    """Убирает мягкие переносы, переносы строк и лишние пробелы для сопоставления заголовков."""
    s: str = (
        text.replace("\u00ad", "")
        .replace("\u00a0", " ")
        .replace("\n", " ")
        .strip()
    )
    return re.sub(r"\s+", " ", s).strip()


# Маппинг заголовков страницы (после нормализации) в поля БД
_HEADER_TO_FIELD: Dict[str, str] = {
    "тип документа": "doc_type",
    "регистрационный номер": "reg_number",
    "дата регистрации (дата уведомления)": "date_registration",
    "регистрирующий орган (организация)": "registering_org",
    "дата наступления основания для опубликования на сайте": "date_ground_publication",
    "дата размещения": "date_placement",
    "файл": "file_url",
}


class _TableParser(HTMLParser):
    """Парсер одной таблицы: первая строка — заголовки, остальные — данные.

    В ячейке со ссылкой <a href="..."> в значение ячейки подставляется href
    (прямая ссылка на файл для колонки «Файл»).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table: bool = False
        self.in_tr: bool = False
        self.in_td: bool = False
        self.current_cell: str = ""
        self.cell_has_href: bool = False
        self.current_row: List[str] = []
        self.rows: List[List[str]] = []
        self.header: List[str] = []
        self.seen_header: bool = False

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif self.in_tr and tag in ("td", "th"):
            self.in_td = True
            self.current_cell = ""
            self.cell_has_href = False
        elif self.in_td and tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.current_cell = v.strip()
                    self.cell_has_href = True
                    break

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.in_tr:
            self.in_tr = False
            if any(cell.strip() for cell in self.current_row):
                if not self.seen_header:
                    self.header = [_normalize_header_cell(c) for c in self.current_row]
                    self.seen_header = True
                else:
                    self.rows.append([c.strip() for c in self.current_row])
        elif tag in ("td", "th") and self.in_td:
            self.in_td = False
            self.current_row.append(self.current_cell.strip())

    def handle_data(self, data: str) -> None:
        if self.in_td and not self.cell_has_href:
            self.current_cell += data


def _extract_table_by_cont_wrap_space_tbl(html_content: str) -> Optional[str]:
    """Находит таблицу по пути #cont_wrap > div.spaceTbl > table (только stdlib, regex)."""
    print(f"[emission_docs] Этап 1: поиск #cont_wrap. Длина HTML={len(html_content)}", flush=True)

    cont_match = re.search(
        r'<div\s+id\s*=\s*["\']cont_wrap["\'][^>]*>',
        html_content,
        re.IGNORECASE,
    )
    if not cont_match:
        print("[emission_docs] Этап 1: не найден <div id=\"cont_wrap\">", flush=True)
        print(f"[emission_docs] Полученный HTML целиком ({len(html_content)} символов):", flush=True)
        print(html_content, flush=True)
        return None
    after_cont: str = html_content[cont_match.end() :]
    print(f"[emission_docs] Этап 1: cont_wrap найден, остаток {len(after_cont)} символов", flush=True)

    space_match = re.search(
        r'<div\s+[^>]*class\s*=\s*["\'][^"\']*spaceTbl[^"\']*["\'][^>]*>',
        after_cont,
        re.IGNORECASE,
    )
    if not space_match:
        print("[emission_docs] Этап 2: не найден div.spaceTbl после cont_wrap", flush=True)
        return None
    after_space: str = after_cont[space_match.end() :]
    print(f"[emission_docs] Этап 2: div.spaceTbl найден, остаток {len(after_space)} символов", flush=True)

    table_open = re.search(r"<table\b", after_space, re.IGNORECASE)
    if not table_open:
        print("[emission_docs] Этап 3: не найден тег <table> после spaceTbl", flush=True)
        return None
    table_start_pos: int = table_open.start()
    fragment: str = after_space[table_start_pos:]
    print(f"[emission_docs] Этап 3: <table> найден, фрагмент {len(fragment)} символов", flush=True)

    depth: int = 0
    pos: int = 0
    while True:
        next_open = re.search(r"<table\b", fragment[pos:], re.IGNORECASE)
        next_close = re.search(r"</table\s*>", fragment[pos:], re.IGNORECASE)
        if next_close is None:
            print("[emission_docs] Этап 4: не найден парный </table>", flush=True)
            return None
        if next_open is not None and next_open.start() + pos < next_close.start() + pos:
            depth += 1
            pos += next_open.end()
        else:
            depth -= 1
            close_end = pos + next_close.end()
            if depth == 0:
                preview: str = fragment[:80].replace("\n", " ")
                print(f"[emission_docs] Этап 4: таблица извлечена, длина={close_end}, превью: {preview}...", flush=True)
                return fragment[:close_end]
            pos = close_end

    return None


def _row_to_document(
    header: List[str],
    row: List[str],
    log_unmapped: bool = False,
) -> Dict[str, Optional[Union[str, int]]]:
    """Превращает строку таблицы (список ячеек) в словарь полей для БД."""
    row_padded: List[str] = row + [""] * (len(header) - len(row))
    raw: Dict[str, str] = dict(zip(header, row_padded))

    doc: Dict[str, Optional[Union[str, int]]] = {
        "doc_type": None,
        "reg_number": None,
        "date_registration": None,
        "registering_org": None,
        "date_ground_publication": None,
        "date_placement": None,
        "file_url": None,
    }

    unmapped: List[str] = []
    for h, value in raw.items():
        key_lower: str = _normalize_header_cell(h).lower()
        field: Optional[str] = _HEADER_TO_FIELD.get(key_lower)
        if field is None:
            if h.strip():
                unmapped.append(repr(key_lower))
            continue
        if not value:
            continue
        if field == "file_url":
            doc[field] = value.strip() or None
        else:
            doc[field] = value.strip() or None

    if log_unmapped and unmapped:
        print(f"[emission_docs] Несопоставленные заголовки (нижний регистр): {unmapped[:10]}", flush=True)

    return doc


def parse_emission_documents(html_content: str) -> List[Dict[str, Optional[Union[str, int]]]]:
    """Извлекает строки таблицы эмиссионных документов из HTML-страницы.

    Таблица ищется только по пути #cont_wrap > div.spaceTbl > table.
    Первая строка таблицы — заголовки, остальные — данные. Результат приводится
    к полям таблицы БД emission_documents.
    """
    print(f"[emission_docs] Старт парсинга, размер HTML={len(html_content or 0)} байт", flush=True)

    table_html: Optional[str] = _extract_table_by_cont_wrap_space_tbl(html_content)
    if table_html is None:
        print("[emission_docs] Таблица не извлечена (cont_wrap/spaceTbl/table). Завершение.", flush=True)
        return []

    parser = _TableParser()
    parser.feed(table_html)

    header_preview: List[str] = [h[:30] for h in parser.header] if parser.header else []
    print(
        f"[emission_docs] Парсер: заголовков={len(parser.header)}, строк данных={len(parser.rows)}. Header={header_preview}",
        flush=True,
    )

    if not parser.header:
        print("[emission_docs] Заголовок таблицы пуст. Завершение.", flush=True)
        return []
    if not parser.rows:
        print("[emission_docs] Нет строк данных после заголовка. Завершение.", flush=True)
        return []

    result: List[Dict[str, Optional[Union[str, int]]]] = []
    skipped_no_doc_type: int = 0
    for i, row in enumerate(parser.rows):
        rec: Dict[str, Optional[Union[str, int]]] = _row_to_document(
            parser.header, row, log_unmapped=(i == 0)
        )
        if rec.get("doc_type"):
            result.append(rec)
        else:
            skipped_no_doc_type += 1

    print(
        f"[emission_docs] Итог: записей для БД={len(result)}, пропущено (нет doc_type)={skipped_no_doc_type}",
        flush=True,
    )
    if result:
        first_url: str = (result[0].get("file_url") or "")[:60]
        print(
            f"[emission_docs] Первая запись: doc_type={result[0].get('doc_type')}, reg_number={result[0].get('reg_number')}, file_url={first_url}",
            flush=True,
        )
    return result
