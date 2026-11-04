"""Парсер таблицы эмиссионных документов с HTML-страницы e-disclosure.ru.

Извлекает данные из таблицы на странице
https://www.e-disclosure.ru/portal/files.aspx?id={id}&type=7.
Таблица ищется по пути #cont_wrap > div.spaceTbl > table.
Используется только стандартная библиотека (html.parser, re).
Результат — список словарей для таблицы БД emission_documents.
"""

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Union, Tuple

_DECISION_HEADER_PHRASE: str = r"РЕШЕНИЕ\s+О\s+ВЫПУСКЕ\s+ЦЕННЫХ\s+БУМАГ"

# Начало раздела 1 (серия ищется только в этом разделе).
# Допускаются варианты: «1. Вид, категория (тип), идентификационные признаки ценных бумаг»
# и «1. Вид, категория (тип), ценных бумаг»; возможны обрамление звёздочками (markdown) и пробелы.
_SECTION_1_START_PHRASE: str = (
    r"\*?\s*1\.\s*Вид[,\s]*категория\s*\(тип\)[,\s]*"
    r"(?:идентификационные\s+признаки\s+)?ценных\s+бумаг\s*\*?"
)

# Граница раздела 2: начало любой строки с "2." (название пункта 2 может быть любым)
_SECTION_2_BOUNDARY_PHRASE: str = r"\n\s*2\.\s"

# Паттерны извлечения серии (проверяются по порядку в блоке раздела 1):
# 1) строка вида «Серия облигаций выпуска: СУБ-Т2-2.»
# 2) строка вида «Серия: *БО-19*» или «Серия: БО-19»
# 3) слово «серии» с последующим значением (например «серии БО-19»)
_SERIES_PATTERNS: Tuple[str, ...] = (
    r"Серия\s+облигаций\s+выпуска\s*:\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9\-]*)",
    r"Серия\s*:\s*\*?\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9\-]*)\s*\*?",
    r"серии\s+([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9\-]*)",
)

_SUBSECTION_2_1_START: str = (
    r"2\.1\.\s*Вид[,\s]*категория\s*\(тип\)[,\s]*серия\s*\(при\s+наличии\)"
)

_SUBSECTION_2_3_START: str = (
    r"2\.3\.\s*Регистрационный\s+номер\s+выпуска\s+ценных\s+бумаг"
    r"\s+и\s+дата\s+его\s+регистрации"
)

_NEXT_SUBSECTION_BOUNDARY: str = r"(?:^\s*(?:##\s*)?(?:2\.\d+|3)\.)"


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
    after_cont: str = html_content[cont_match.end():]
    print(f"[emission_docs] Этап 1: cont_wrap найден, остаток {len(after_cont)} символов", flush=True)

    space_match = re.search(
        r'<div\s+[^>]*class\s*=\s*["\'][^"\']*spaceTbl[^"\']*["\'][^>]*>',
        after_cont,
        re.IGNORECASE,
    )
    if not space_match:
        print("[emission_docs] Этап 2: не найден div.spaceTbl после cont_wrap", flush=True)
        return None
    after_space: str = after_cont[space_match.end():]
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


def extract_series_from_markdown(md_text: str) -> Optional[str]:
    """Извлекает серию облигации только из раздела 1 документа «Решение о выпуске ценных бумаг».

    В рассмотрение берётся только текст, где есть заголовок «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ».
    Раздел 1 может иметь вид «1. Вид, категория (тип), ценных бумаг» или с фразой
    «идентификационные признаки»; допускается обрамление звёздочками (markdown).
    Серия извлекается из блока раздела 1 до начала раздела 2 (строка с «2.»).
    Поддерживаемые форматы в тексте: «Серия облигаций выпуска: СУБ-Т2-2.»,
    «Серия: *БО-19*» (или «Серия: БО-19»), либо слово «серии» с последующим значением.

    Args:
        md_text: Полный текст markdown-документа.

    Returns:
        Значение серии (например «БО-19», «ПБО-002Р-31») или ``None``, если не найдено.
    """
    if not md_text or not md_text.strip():
        print("  [SERIES] extract: входной текст пуст", flush=True)
        return None

    print(
        f"  [SERIES] extract: входной текст {len(md_text)} символов",
        flush=True,
    )

    try:
        header_match: Optional[re.Match[str]] = re.search(
            _DECISION_HEADER_PHRASE, md_text, re.IGNORECASE
        )
        if not header_match:
            print(
                "  [SERIES] extract: заголовок «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ» не найден",
                flush=True,
            )
            return None
        print(
            f"  [SERIES] extract: заголовок найден на позиции {header_match.start()}",
            flush=True,
        )

        text_after_header: str = md_text[header_match.start():]

        section_1_match: Optional[re.Match[str]] = re.search(
            _SECTION_1_START_PHRASE, text_after_header, re.IGNORECASE
        )
        if not section_1_match:
            print(
                "  [SERIES] extract: раздел 1 (идентификационные признаки) не найден",
                flush=True,
            )
            return None

        # Текст раздела 1: от начала раздела 1 до первой строки с «2.» (название пункта 2 любое)
        text_from_section_1: str = text_after_header[section_1_match.start():]
        section_2_match: Optional[re.Match[str]] = re.search(
            _SECTION_2_BOUNDARY_PHRASE, text_from_section_1
        )
        if section_2_match:
            block: str = text_from_section_1[: section_2_match.start()]
        else:
            block = text_from_section_1

        print(
            f"  [SERIES] extract: блок раздела 1 (до «2.») — {len(block)} символов",
            flush=True,
        )

        series_value: Optional[str] = None
        for pattern in _SERIES_PATTERNS:
            series_match = re.search(pattern, block, re.IGNORECASE)
            if series_match:
                series_value = series_match.group(1).strip()
                break
        if not series_value:
            print(
                "  [SERIES] extract: ни один паттерн серии не найден в разделе 1",
                flush=True,
            )
            return None

        print(f"  [SERIES] extract: серия извлечена → {series_value!r}", flush=True)
        return series_value

    except re.error as exc:
        print(f"  [SERIES] extract: ошибка regex — {exc}", flush=True)
        return None
