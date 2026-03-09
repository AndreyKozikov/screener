"""Парсер серии облигации из markdown и алгоритм выбора события по secid/рег.номеру/серии.

Извлекает серию облигации из текста документа «Решение о выпуске ценных бумаг»,
выделяет подразделы 2.1 и 2.3 из текста события и реализует трёхшаговый fallback
для поиска нужного события: secid → рег. номер → серия.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.utils.edisclosure_utils import (
    event_text_matches_reg_number,
    normalize_reg_number,
)

# ---------------------------------------------------------------------------
# Константы: маркеры / regex-фразы для парсинга
# ---------------------------------------------------------------------------

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
# 1) строка вида «Серия: *БО-19*» или «Серия: БО-19»
# 2) слово «серии» с последующим значением (например «серии БО-19»)
_SERIES_PATTERNS: Tuple[str, ...] = (
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


# ---------------------------------------------------------------------------
# Шаг 1: извлечение серии облигации из markdown-текста
# ---------------------------------------------------------------------------


def markdown_has_decision_header(md_text: str) -> bool:
    """Проверяет наличие заголовка «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ» в тексте (без учёта регистра)."""
    if not md_text or not md_text.strip():
        return False
    return bool(re.search(_DECISION_HEADER_PHRASE, md_text, re.IGNORECASE))


def extract_series_from_markdown(md_text: str) -> Optional[str]:
    """Извлекает серию облигации только из раздела 1 документа «Решение о выпуске ценных бумаг».

    В рассмотрение берётся только текст, где есть заголовок «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ».
    Раздел 1 может иметь вид «1. Вид, категория (тип), ценных бумаг» или с фразой
    «идентификационные признаки»; допускается обрамление звёздочками (markdown).
    Серия извлекается из блока раздела 1 до начала раздела 2 (строка с «2.»).
    Поддерживаемые форматы в тексте: строка «Серия: *БО-19*» (или «Серия: БО-19»),
    либо слово «серии» с последующим значением (например «серии БО-19»).

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
                "  [SERIES] extract: ни один паттерн серии (Серия: ... / серии ...) не найден в разделе 1",
                flush=True,
            )
            return None

        print(f"  [SERIES] extract: серия извлечена → {series_value!r}", flush=True)
        return series_value

    except re.error as exc:
        print(f"  [SERIES] extract: ошибка regex — {exc}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Шаг 3: извлечение подразделов 2.1 и 2.3 из текста события
# ---------------------------------------------------------------------------


def extract_event_subsections_2_1_and_2_3(event_full_text: str) -> str:
    """Выделяет подразделы 2.1 и 2.3 из полного текста события и возвращает их объединение.

    Подраздел 2.1 — «Вид, категория (тип), серия (при наличии) и иные
    идентификационные признаки размещаемых ценных бумаг».
    Подраздел 2.3 — «Регистрационный номер выпуска ценных бумаг и дата его регистрации».

    Каждый подраздел ограничен следующим подразделом (2.2, 2.3, 2.4, 3. и т.д.).

    Args:
        event_full_text: Полный текст события (HTML→plain text).

    Returns:
        Объединённый текст подразделов 2.1 + 2.3. Пустая строка, если ничего не найдено.
    """
    if not event_full_text or not event_full_text.strip():
        return ""

    subsection_2_1: str = _extract_subsection(
        event_full_text, _SUBSECTION_2_1_START, label="2.1"
    )
    subsection_2_3: str = _extract_subsection(
        event_full_text, _SUBSECTION_2_3_START, label="2.3"
    )

    combined: str = f"{subsection_2_1}\n{subsection_2_3}".strip()
    print(
        f"  [SUBSECTIONS] 2.1={len(subsection_2_1)} симв., "
        f"2.3={len(subsection_2_3)} симв., итого={len(combined)} симв.",
        flush=True,
    )
    return combined


def _extract_subsection(
    text: str,
    start_pattern: str,
    label: str = "",
) -> str:
    """Извлекает один подраздел от ``start_pattern`` до следующего подраздела.

    Args:
        text: Полный текст события.
        start_pattern: Regex-паттерн начала подраздела.
        label: Метка для логирования.

    Returns:
        Текст подраздела или пустая строка, если начало не найдено.
    """
    start_match: Optional[re.Match[str]] = re.search(
        start_pattern, text, re.IGNORECASE | re.DOTALL
    )
    if not start_match:
        print(f"  [SUBSECTIONS] подраздел {label} не найден", flush=True)
        return ""

    remaining: str = text[start_match.start():]

    end_match: Optional[re.Match[str]] = re.search(
        _NEXT_SUBSECTION_BOUNDARY,
        remaining[1:],
        re.MULTILINE | re.IGNORECASE,
    )
    if end_match:
        subsection: str = remaining[: end_match.start() + 1]
    else:
        subsection = remaining

    return subsection.strip()


# ---------------------------------------------------------------------------
# Шаг 2: функции сопоставления (secid / рег. номер / серия)
# ---------------------------------------------------------------------------


def event_matches_secid(subsection_text: str, secid: str) -> bool:
    """Проверяет наличие SECID облигации в тексте события.

    Ищет secid как целое слово (с учётом границ ``\\b``), без учёта регистра.

    Args:
        subsection_text: Полный текст события (или фрагмент для поиска).
        secid: Идентификатор ценной бумаги (например «RU000A107UQ9»).

    Returns:
        ``True``, если secid найден; иначе ``False``.
    """
    if not subsection_text or not secid or not secid.strip():
        return False

    secid_clean: str = secid.strip()
    pattern: str = r"\b" + re.escape(secid_clean) + r"\b"

    try:
        found: bool = bool(re.search(pattern, subsection_text, re.IGNORECASE))
    except re.error as exc:
        print(f"  [MATCH SECID] ошибка regex — {exc}", flush=True)
        return False

    print(
        f"  [MATCH SECID] secid={secid_clean!r} → {'найден' if found else 'не найден'}",
        flush=True,
    )
    return found


def event_matches_reg_number(subsection_text: str, reg_number: str) -> bool:
    """Проверяет наличие регистрационного номера в тексте события.

    Делегирует проверку в ``event_text_matches_reg_number`` из
    ``app.utils.edisclosure_utils`` (только полное совпадение номера, без паттернов по частям).

    Args:
        subsection_text: Полный текст события (или фрагмент для поиска).
        reg_number: Регистрационный номер облигации (например «4B02-01-36245-A-001P»).

    Returns:
        ``True``, если рег. номер найден; иначе ``False``.
    """
    if not subsection_text or not reg_number or not reg_number.strip():
        return False

    reg_number_clean: str = reg_number.strip()

    try:
        reg_num_ru: str
        reg_num_lat: str
        reg_num_ru, reg_num_lat = normalize_reg_number(reg_number_clean)
        found: bool = event_text_matches_reg_number(
            subsection_text, reg_num_ru, reg_num_lat
        )
    except Exception as exc:
        print(f"  [MATCH REG_NUMBER] ошибка проверки — {exc}", flush=True)
        return False

    print(
        f"  [MATCH REG_NUMBER] reg_number={reg_number_clean!r} → "
        f"{'найден' if found else 'не найден'}",
        flush=True,
    )
    return found


def event_matches_series(
    subsection_text: str,
    series: Optional[str],
) -> bool:
    """Проверяет наличие серии облигации в тексте события.

    Ищет значение серии как подстроку, допуская произвольные пробелы/переносы
    между символами дефиса, без учёта регистра.

    Args:
        subsection_text: Полный текст события (или фрагмент для поиска).
        series: Серия облигации (например «ПБО-002Р-31») или ``None``.

    Returns:
        ``True``, если серия найдена; ``False``, если серия пуста/None или не найдена.
    """
    if not series or not series.strip():
        print("  [MATCH SERIES] серия не задана → False", flush=True)
        return False
    if not subsection_text:
        return False

    series_clean: str = series.strip()

    parts: List[str] = series_clean.split("-")
    flexible_pattern: str = r"\s*[\-–—]\s*".join(re.escape(p) for p in parts)

    try:
        found: bool = bool(
            re.search(flexible_pattern, subsection_text, re.IGNORECASE)
        )
    except re.error as exc:
        print(f"  [MATCH SERIES] ошибка regex — {exc}", flush=True)
        return False

    print(
        f"  [MATCH SERIES] series={series_clean!r} → "
        f"{'найден' if found else 'не найден'}",
        flush=True,
    )
    return found


# ---------------------------------------------------------------------------
# Шаг 2 (главная функция): отбор всех событий по условиям secid / рег.номер / серия
# ---------------------------------------------------------------------------


def filter_events_by_secid_regnumber_series(
    events: List[Dict[str, Any]],
    secid: str,
    reg_number: str,
    series: Optional[str],
) -> List[Dict[str, Any]]:
    """Отбирает из списка все события, проходящие по одному из условий в полном тексте события.

    Для каждого события проверяет по полному тексту (full_text):
      - совпадение по SECID, или
      - совпадение по регистрационному номеру, или
      - совпадение по серии облигации.
    Событие попадает в результат, если выполняется хотя бы одно условие.

    Args:
        events: Список словарей событий; каждый должен содержать ключ ``"full_text"``.
        secid: Идентификатор ценной бумаги.
        reg_number: Регистрационный номер облигации.
        series: Серия облигации (может быть ``None``).

    Returns:
        Список всех событий, прошедших отбор (может быть пустым).
    """
    if not events:
        print("  [FILTER EVENTS] список событий пуст → []", flush=True)
        return []

    print(
        f"  [FILTER EVENTS] Отбор из {len(events)} событий по secid/рег.номеру/серии "
        f"(полный текст события) (secid={secid!r}, reg_number={reg_number!r}, series={series!r})",
        flush=True,
    )

    result: List[Dict[str, Any]] = []
    for event in events:
        full_text: str = event.get("full_text", "")
        if event_matches_secid(full_text, secid):
            result.append(event)
            print(
                f"  [FILTER EVENTS] ✓ событие {event.get('event_name', '')!r} "
                f"({event.get('event_date', '')}) — совпадение по secid",
                flush=True,
            )
        elif event_matches_reg_number(full_text, reg_number):
            result.append(event)
            print(
                f"  [FILTER EVENTS] ✓ событие {event.get('event_name', '')!r} "
                f"({event.get('event_date', '')}) — совпадение по рег.номеру",
                flush=True,
            )
        elif event_matches_series(full_text, series):
            result.append(event)
            print(
                f"  [FILTER EVENTS] ✓ событие {event.get('event_name', '')!r} "
                f"({event.get('event_date', '')}) — совпадение по серии",
                flush=True,
            )

    print(
        f"  [FILTER EVENTS] Итого отобрано событий: {len(result)}",
        flush=True,
    )
    return result


def select_event_by_secid_regnumber_series(
    events: List[Dict[str, Any]],
    secid: str,
    reg_number: str,
    series: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Выбирает одно событие из списка по трёхшаговому fallback-алгоритму.

    Для каждого события по полному тексту последовательно проверяет:
      1. Совпадение по SECID.
      2. Совпадение по регистрационному номеру (если шаг 1 не дал результата).
      3. Совпадение по серии облигации (если шаг 2 не дал результата).

    Args:
        events: Список словарей событий; каждый должен содержать ключ ``"full_text"``.
        secid: Идентификатор ценной бумаги.
        reg_number: Регистрационный номер облигации.
        series: Серия облигации (может быть ``None``).

    Returns:
        Словарь выбранного события или ``None``, если ни один шаг не сработал.
    """
    filtered: List[Dict[str, Any]] = filter_events_by_secid_regnumber_series(
        events, secid, reg_number, series
    )
    if not filtered:
        return None
    return filtered[0]
