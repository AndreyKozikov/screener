"""Утилиты для работы с e-disclosure.ru.

Предоставляет функции поиска компаний по ИНН и поиска событий по
регистрационному номеру облигации.
"""

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

# Кэш сессии и токена
_SESSION_CACHE: Dict[str, Optional[Any]] = {
    "session": None,  # type: Optional[requests.Session]
    "token": None,    # type: Optional[str]
}

# Заголовки для API запросов
_API_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "ru,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.e-disclosure.ru",
    "Referer": "https://www.e-disclosure.ru/poisk-po-kompaniyam",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# Заголовки для HTML страниц
_HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
}

_URL = "https://www.e-disclosure.ru/api/search/companies"
_EVENTS_URL = "https://www.e-disclosure.ru/api/events/page"
_EVENT_PAGE_URL = "https://www.e-disclosure.ru/portal/event.aspx"
_SEARCH_PAGE_URL = "https://www.e-disclosure.ru/poisk-po-kompaniyam"
_MAIN_PAGE_URL = "https://www.e-disclosure.ru"
_TIMEOUT = 30  # Увеличен таймаут для медленных соединений

_MOEX_DISCLOSURE_TREE_URL = "https://web.moex.com/moex-web-icdb-api/api/v1/bond-disclosure-tree/reporting"
_MOEX_FILE_BASE_URL = "https://fs.moex.com/emidocs"

_TARGET_DOC_TYPES = (
    "Решение о выпуске (дополнительном выпуске) ценных бумаг",
    "Документ, содержащий условия размещения ценных бумаг",
)

# Карта визуально идентичных символов: Кириллица → Латиница.
# Включены только пары с действительно совпадающим начертанием в обоих алфавитах.
_CHAR_MAP: Dict[str, str] = {
    "А": "A", "В": "B", "С": "C", "Е": "E", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X",
    # Строчные (исключены в/b и т/t — начертание не совпадает)
    "а": "a", "с": "c", "е": "e", "к": "k",
    "м": "m", "о": "o", "р": "p", "х": "x",
}


def _get_session_data() -> Tuple[requests.Session, str]:
    """Получает сессию и токен через requests."""
    session = requests.Session()
    session.headers.update(_API_HEADERS)
    
    # Получаем страницу поиска для получения токена и кук
    response = session.get(_SEARCH_PAGE_URL, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    response.raise_for_status()
    
    # Извлекаем токен из HTML
    token_match = re.search(
        r'<input[^>]*name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']',
        response.text,
        re.IGNORECASE
    )
    
    if not token_match:
        raise RuntimeError("Не удалось найти токен __RequestVerificationToken на странице")
    
    token = token_match.group(1)
    return session, token


def _clear_session_cache() -> None:
    """Очищает кэш сессии и токена."""
    global _SESSION_CACHE
    _SESSION_CACHE["session"] = None
    _SESSION_CACHE["token"] = None


def _get_session() -> Tuple[requests.Session, str]:
    """Инициализирует сессию и получает токен антифоргери."""
    global _SESSION_CACHE

    if _SESSION_CACHE["session"] is not None and _SESSION_CACHE["token"] is not None:
        return _SESSION_CACHE["session"], _SESSION_CACHE["token"]

    session, token = _get_session_data()
    _SESSION_CACHE["session"] = session
    _SESSION_CACHE["token"] = token
    return session, token


def search_company_by_inn(inn: str) -> List[Dict[str, Any]]:
    """Ищет компанию по ИНН на e-disclosure.ru и возвращает id, name, district, region, branch.

    Args:
        inn: ИНН компании (например, 7712040126).

    Returns:
        Список словарей с полями: id, name, district, region, branch для каждой найденной компании.
    """
    print(f"[E-DISCLOSURE SEARCH] Старт поиска компании: ИНН={inn}")
    # Очищаем кэш перед каждым поиском компании
    _clear_session_cache()

    print(f"[E-DISCLOSURE SEARCH] Получение сессии и токена: GET {_SEARCH_PAGE_URL}")
    session, token = _get_session()

    data = {
        "textfield": inn,
        "radReg": "FederalDistricts",
        "districtsCheckboxGroup": "-1",
        "regionsCheckboxGroup": "-1",
        "branchesCheckboxGroup": "-1",
        "lastPageSize": "10",
        "lastPageNumber": "1",
        "query": inn,
    }
    data["__RequestVerificationToken"] = token

    print(f"[E-DISCLOSURE SEARCH] → POST {_URL} | query={inn}")
    response = session.post(_URL, data=data, timeout=_TIMEOUT)
    print(f"[E-DISCLOSURE SEARCH] HTTP {response.status_code}")

    if response.status_code == 403:
        print("[E-DISCLOSURE SEARCH] 403 — обновляем сессию и повторяем запрос")
        _clear_session_cache()
        session, token = _get_session()
        data["__RequestVerificationToken"] = token
        response = session.post(_URL, data=data, timeout=_TIMEOUT)
        print(f"[E-DISCLOSURE SEARCH] Повторный запрос HTTP {response.status_code}")

    response.raise_for_status()
    payload = response.json()

    found_list = payload.get("foundCompaniesList") or []
    print(f"[E-DISCLOSURE SEARCH] Найдено компаний: {len(found_list)}")

    result: List[Dict[str, Any]] = []
    for item in found_list:
        result.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "district": item.get("district"),
            "region": item.get("region"),
            "branch": item.get("branch"),
        })
        print(f"[E-DISCLOSURE SEARCH]   id={item.get('id')}, name={item.get('name')}")

    return result


def _extract_event_text(pseudo_guid: str, session: requests.Session) -> Optional[str]:
    """Извлекает текст события из HTML страницы по pseudoGUID.
    
    Args:
        pseudo_guid: Псевдо-GUID события.
        session: Сессия requests для выполнения запросов.
    
    Returns:
        Извлечённый текст или None, если не удалось извлечь.
    """
    page_url = f"{_EVENT_PAGE_URL}?EventId={pseudo_guid}"
    # Для HTML страницы явно исключаем X-Requested-With из заголовков запроса
    html_headers = {k: v for k, v in _HTML_HEADERS.items()}
    html_headers.pop("X-Requested-With", None)
    page_response = session.get(page_url, headers=html_headers, timeout=_TIMEOUT)
    page_response.raise_for_status()
    page_html = page_response.text

    # Извлекаем div#cont_wrap
    cont_wrap_match = re.search(
        r'<div\s+id="cont_wrap"[^>]*>',
        page_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not cont_wrap_match:
        return None

    start_pos = cont_wrap_match.end()
    depth = 1
    pos = start_pos
    while pos < len(page_html) and depth > 0:
        next_div_open = page_html.find("<div", pos)
        next_div_close = page_html.find("</div>", pos)
        if next_div_open == -1:
            next_div_open = len(page_html)
        if next_div_close == -1:
            next_div_close = len(page_html)
        if next_div_close < next_div_open:
            depth -= 1
            pos = next_div_close + 6
        else:
            depth += 1
            pos = next_div_open + 4
    cont_wrap_content = page_html[start_pos:pos - 6]

    # Ищем второй вложенный div с style word-break: break-word; ...
    div_pattern = (
        r'<div\s+style="[^"]*word-break:\s*break-word[^"]*"[^>]*>'
    )
    div_matches = list(re.finditer(div_pattern, cont_wrap_content, re.IGNORECASE))
    if not div_matches:
        return None
    # Берём второй div (второй вложенный блок)
    target_match = div_matches[1] if len(div_matches) > 1 else div_matches[0]

    content_start = target_match.end()
    # Извлекаем содержимое до соответствующего </div> (учитывая вложенные div)
    depth = 1
    pos = content_start
    content_end = -1
    while pos < len(cont_wrap_content) and depth > 0:
        next_open = cont_wrap_content.find("<div", pos)
        next_close = cont_wrap_content.find("</div>", pos)
        if next_open == -1:
            next_open = len(cont_wrap_content)
        if next_close == -1:
            break
        if next_close < next_open:
            depth -= 1
            if depth == 0:
                content_end = next_close
            pos = next_close + 6
        else:
            depth += 1
            pos = next_open + 4
    if content_end == -1:
        return None

    text = cont_wrap_content[content_start:content_end]
    text = re.sub(r"<[^>]+>", "", text)  # удаляем оставшиеся теги
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = html.unescape(text)  # декодируем &#171;, &#187; и прочие HTML-сущности
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)  # удаляем управляющие символы
    text = text.strip()

    return text


def _format_event_date(event_date_str: Optional[str]) -> Optional[str]:
    """Преобразует ISO-дату события в формат YYYY-MM-DD."""
    if not event_date_str:
        return None
    try:
        return datetime.fromisoformat(
            event_date_str.replace("Z", "+00:00")
        ).date().isoformat()
    except (ValueError, TypeError):
        return None


def _normalize_reg_number(reg_number: str) -> Tuple[str, str]:
    """Создаёт две нормализованные копии регистрационного номера.

    На основе карты ``_CHAR_MAP`` формирует:

    - ``reg_num_ru``: все символы из карты заменены на кириллические эквиваленты.
    - ``reg_num_lat``: все символы из карты заменены на латинские эквиваленты.

    Args:
        reg_number: Регистрационный номер облигации.

    Returns:
        Кортеж ``(reg_num_ru, reg_num_lat)``.
    """
    reverse_map: Dict[str, str] = {lat: ru for ru, lat in _CHAR_MAP.items()}
    reg_num_ru = "".join(reverse_map.get(ch, ch) for ch in reg_number)
    reg_num_lat = "".join(_CHAR_MAP.get(ch, ch) for ch in reg_number)
    return reg_num_ru, reg_num_lat


def _parse_reg_number_parts(reg_number: str) -> Optional[Tuple[str, str, str]]:
    """Разбирает регистрационный номер на составные части.

    Ожидаемая структура::

        XXXX-<порядковый_номер>-<ХХХХ>-<Х>-<номер_программы>

    Например: ``4B02-01-36245-A-001P``

    - ``parts[0]`` — 4-символьный префикс (пропускается).
    - ``parts[1]`` — порядковый номер выпуска (2 символа).
    - ``parts[2]-parts[3]`` — код эмитента формата ``ХХХХ-Х``.
    - ``parts[4]`` — номер программы выпуска (4 символа).

    Args:
        reg_number: Нормализованный регистрационный номер облигации.

    Returns:
        Кортеж ``(serial_num, emitent_code, program_num)`` или ``None``,
        если номер не соответствует ожидаемой структуре.
    """
    parts = reg_number.split("-")
    if len(parts) < 5:
        return None

    serial_num: str = parts[1]
    emitent_code: str = f"{parts[2]}-{parts[3]}"
    program_num: str = parts[4]
    return serial_num, emitent_code, program_num


def _event_text_matches_reg_number(
    text: str,
    reg_num_ru: str,
    reg_num_lat: str,
    parts_ru: Optional[Tuple[str, str, str]],
    parts_lat: Optional[Tuple[str, str, str]],
) -> bool:
    """Проверяет, содержит ли текст события регистрационный номер или его части.

    Сначала выполняется полное совпадение (кириллическая и латинская копии),
    затем частичное по парам ``<номер_программы>-<порядковый_номер>`` и
    ``<код_эмитента>-<номер_программы>``.

    Args:
        text: Текст события.
        reg_num_ru: Регистрационный номер в кириллической нормализации.
        reg_num_lat: Регистрационный номер в латинской нормализации.
        parts_ru: Разобранные части кириллической копии или ``None``.
        parts_lat: Разобранные части латинской копии или ``None``.

    Returns:
        ``True``, если совпадение найдено; иначе ``False``.
    """
    if not reg_num_ru:
        return False

    text_lower = text.lower()

    if reg_num_ru.lower() in text_lower or reg_num_lat.lower() in text_lower:
        return True

    for parts in (parts_ru, parts_lat):
        if parts is None:
            continue
        serial_num, emitent_code, program_num = parts
        pattern1 = f"{program_num}-{serial_num}"
        if pattern1.lower() in text_lower:
            return True
        pattern2 = f"{emitent_code}-{program_num}"
        if pattern2.lower() in text_lower:
            return True

    return False


def _find_all_events_sorted_by_date(
    events: List[Dict[str, Any]],
    date_obj: datetime.date,
) -> List[Dict[str, Any]]:
    """Возвращает все события строго раньше ``date_obj``, отсортированные от новых к старым.

    Не фильтрует по названию события — включаются события любого типа.

    Args:
        events: Список событий, полученных от API.
        date_obj: Граничная дата (события с этой датой и позже исключаются).

    Returns:
        Список событий, отсортированных по дате (от более поздних к более ранним).
    """
    filtered: List[Tuple[datetime.date, Dict[str, Any]]] = []
    for event in events:
        event_date_str = event.get("eventDate")
        if not event_date_str:
            continue
        try:
            event_date = datetime.fromisoformat(
                event_date_str.replace("Z", "+00:00")
            ).date()
        except (ValueError, TypeError):
            continue
        if event_date >= date_obj:
            continue
        filtered.append((event_date, event))
    filtered.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in filtered]


def find_events_by_reg_number(
    date: str,
    company_id: int,
    reg_number: str,
) -> List[Dict[str, Optional[str]]]:
    """Загружает все события компании за год и возвращает те, что содержат регистрационный номер.

    Перебирает все события выбранного года (строго раньше ``date``) в порядке убывания даты.
    Для каждого события загружает текст со страницы и проверяет наличие регистрационного номера
    или его частей. Возвращает все совпавшие события; год не меняется.

    Args:
        date: Граничная дата в формате YYYY-MM-DD. Включаются только события строго раньше неё.
        company_id: ID компании на e-disclosure.ru.
        reg_number: Регистрационный номер облигации.

    Returns:
        Список словарей с полями ``event_name``, ``event_date`` (``None``, если дата не распознана),
        ``text`` для каждого события, в котором найден регистрационный номер или его части.
        Пустой список, если ``reg_number`` пустой или совпадений не найдено.
    """
    if not reg_number.strip():
        print("[E-DISCLOSURE EVENTS] рег.номер пустой — поиск событий пропущен")
        return []

    print(f"[E-DISCLOSURE EVENTS] Старт: company_id={company_id}, рег.номер={reg_number}, дата={date}")
    session, _ = _get_session()

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    year = date_obj.year

    params = {"companyId": company_id, "year": year}
    events_url_full = f"{_EVENTS_URL}?companyId={company_id}&year={year}"
    print(f"[E-DISCLOSURE EVENTS] → GET {events_url_full}")
    response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    print(f"[E-DISCLOSURE EVENTS] HTTP {response.status_code}")
    if response.status_code == 403:
        print("[E-DISCLOSURE EVENTS] 403 — обновляем сессию и повторяем запрос")
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
        print(f"[E-DISCLOSURE EVENTS] Повторный запрос HTTP {response.status_code}")
    response.raise_for_status()
    events = response.json()
    print(f"[E-DISCLOSURE EVENTS] Всего событий за {year} год: {len(events)}")

    sorted_events = _find_all_events_sorted_by_date(events, date_obj)
    print(f"[E-DISCLOSURE EVENTS] После фильтрации по дате (< {date}): {len(sorted_events)} событий")

    reg_num_ru, reg_num_lat = _normalize_reg_number(reg_number)
    parts_ru: Optional[Tuple[str, str, str]] = _parse_reg_number_parts(reg_num_ru)
    parts_lat: Optional[Tuple[str, str, str]] = _parse_reg_number_parts(reg_num_lat)
    print(f"[E-DISCLOSURE EVENTS] Нормализация рег.номера: RU={reg_num_ru}, LAT={reg_num_lat}")

    result: List[Dict[str, Optional[str]]] = []
    for idx, event in enumerate(sorted_events, start=1):
        pseudo_guid = event.get("pseudoGUID")
        event_name = event.get("eventName") or "(без названия)"
        event_date_raw = event.get("eventDate", "")
        if not pseudo_guid:
            print(f"[E-DISCLOSURE EVENTS]   [{idx}/{len(sorted_events)}] {event_name} — нет pseudoGUID, пропуск")
            continue
        page_url = f"{_EVENT_PAGE_URL}?EventId={pseudo_guid}"
        print(f"[E-DISCLOSURE EVENTS]   [{idx}/{len(sorted_events)}] → GET {page_url}")
        print(f"[E-DISCLOSURE EVENTS]     Событие: {event_name} ({event_date_raw})")
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            print(f"[E-DISCLOSURE EVENTS]     Текст не извлечён — пропуск")
            continue
        if _event_text_matches_reg_number(text, reg_num_ru, reg_num_lat, parts_ru, parts_lat):
            event_date = _format_event_date(event.get("eventDate"))
            result.append({
                "event_name": event.get("eventName") or "",
                "event_date": event_date,
                "text": text,
            })
            print(f"[E-DISCLOSURE EVENTS]     ✓ СОВПАДЕНИЕ: рег.номер найден в тексте")
        else:
            print(f"[E-DISCLOSURE EVENTS]     — рег.номер не найден")

    print(f"[E-DISCLOSURE EVENTS] Итого совпавших событий: {len(result)}")
    return result


def fetch_moex_disclosure_docs(
    emitent_id: int,
    reg_number: str,
) -> List[Tuple[str, bytes]]:
    """Навигирует по дереву раскрытия MOEX и скачивает PDF-документы по выпуску облигации.

    Выполняет трёхуровневую навигацию по MOEX bond disclosure tree API:
    программа → выпуск → документы. Скачивает PDF-файлы целевых типов документов
    и возвращает их содержимое вместе с именами файлов.

    Args:
        emitent_id: MOEX ID эмитента (moex_id из таблицы emitents).
        reg_number: Регистрационный номер облигации.

    Returns:
        Список кортежей ``(filename, content)`` для каждого скачанного документа.
        Пустой список, если ничего не найдено.
    """
    print(f"[MOEX DOCS] Старт: emitent_id={emitent_id}, reg_number={reg_number}")

    reg_num_ru, reg_num_lat = _normalize_reg_number(reg_number)
    print(f"[MOEX DOCS] Нормализация: RU={reg_num_ru}, LAT={reg_num_lat}")

    parts_ru = _parse_reg_number_parts(reg_num_ru)
    parts_lat = _parse_reg_number_parts(reg_num_lat)
    print(f"[MOEX DOCS] Части RU: {parts_ru}")
    print(f"[MOEX DOCS] Части LAT: {parts_lat}")

    search_patterns: List[Tuple[str, str]] = []
    for parts, reg_num in ((parts_ru, reg_num_ru), (parts_lat, reg_num_lat)):
        if parts is not None:
            _, emitent_code, program_num = parts
            search_patterns.append((f"{emitent_code}-{program_num}", reg_num))

    print(f"[MOEX DOCS] Паттерны поиска: {search_patterns}")
    if not search_patterns:
        print("[MOEX DOCS] Паттерны пустые — выход")
        return []

    moex_headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    program_tree_id = _find_program_tree_id(emitent_id, search_patterns, moex_headers)
    print(f"[MOEX DOCS] Шаг 1 — program_tree_id: {program_tree_id}")
    if program_tree_id is None:
        print("[MOEX DOCS] Программа не найдена — выход")
        return []

    issue_tree_id = _find_issue_tree_id(emitent_id, program_tree_id, search_patterns, moex_headers)
    print(f"[MOEX DOCS] Шаг 2 — issue_tree_id: {issue_tree_id}")
    if issue_tree_id is None:
        print("[MOEX DOCS] Выпуск не найден — выход")
        return []

    target_links = _find_doc_links(emitent_id, issue_tree_id, moex_headers)
    print(f"[MOEX DOCS] Шаг 3 — target_links: {target_links}")
    if not target_links:
        print("[MOEX DOCS] Документы не найдены — выход")
        return []

    downloaded = _download_docs(target_links, moex_headers)
    print(f"[MOEX DOCS] Шаг 4 — скачано файлов: {len(downloaded)}, имена: {[f for f, _ in downloaded]}")
    return downloaded


def _find_program_tree_id(
    emitent_id: int,
    search_patterns: List[Tuple[str, str]],
    headers: Dict[str, str],
) -> Optional[str]:
    """Ищет treeId программы выпуска в дереве раскрытия MOEX.

    Args:
        emitent_id: MOEX ID эмитента.
        search_patterns: Список пар ``(program_pattern, full_reg_num)``.
        headers: HTTP-заголовки для запроса.

    Returns:
        treeId программы или ``None``, если совпадение не найдено.
    """
    url = f"{_MOEX_DISCLOSURE_TREE_URL}/{emitent_id}"
    print(f"[MOEX STEP1] GET {url}")
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        print(f"[MOEX STEP1] HTTP {response.status_code}")
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException as exc:
        print(f"[MOEX STEP1] Ошибка запроса: {exc}")
        return None

    nodes: List[Dict[str, Any]] = data.get("nodes") or []
    print(f"[MOEX STEP1] Получено узлов: {len(nodes)}")
    for node in nodes:
        display_raw: str = node.get("treeDisplayAdditional") or ""
        display = display_raw.lower()
        for program_pattern, _ in search_patterns:
            if program_pattern.lower() in display:
                tree_id = node.get("treeId")
                print(f"[MOEX STEP1] Совпадение: паттерн='{program_pattern}' в '{display_raw}' → treeId={tree_id}")
                return tree_id
        print(f"[MOEX STEP1]   Узел не совпал: '{display_raw}'")
    print("[MOEX STEP1] Ни один узел не совпал")
    return None


def _find_issue_tree_id(
    emitent_id: int,
    program_tree_id: str,
    search_patterns: List[Tuple[str, str]],
    headers: Dict[str, str],
) -> Optional[str]:
    """Ищет treeId конкретного выпуска облигации внутри программы.

    Args:
        emitent_id: MOEX ID эмитента.
        program_tree_id: treeId программы выпуска.
        search_patterns: Список пар ``(program_pattern, full_reg_num)``.
        headers: HTTP-заголовки для запроса.

    Returns:
        treeId выпуска или ``None``, если совпадение не найдено.
    """
    url = f"{_MOEX_DISCLOSURE_TREE_URL}/{emitent_id}/{program_tree_id}"
    print(f"[MOEX STEP2] GET {url}")
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        print(f"[MOEX STEP2] HTTP {response.status_code}")
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException as exc:
        print(f"[MOEX STEP2] Ошибка запроса: {exc}")
        return None

    nodes: List[Dict[str, Any]] = data.get("nodes") or []
    print(f"[MOEX STEP2] Получено узлов: {len(nodes)}")
    for node in nodes:
        display_raw: str = node.get("treeDisplayAdditional") or ""
        display = display_raw.lower()
        for _, full_reg_num in search_patterns:
            if full_reg_num.lower() in display:
                tree_id = node.get("treeId")
                print(f"[MOEX STEP2] Совпадение: рег.номер='{full_reg_num}' в '{display_raw}' → treeId={tree_id}")
                return tree_id
        print(f"[MOEX STEP2]   Узел не совпал: '{display_raw}'")
    print("[MOEX STEP2] Ни один узел не совпал")
    return None


def _find_doc_links(
    emitent_id: int,
    issue_tree_id: str,
    headers: Dict[str, str],
) -> List[str]:
    """Извлекает ссылки на целевые документы из дерева раскрытия.

    Args:
        emitent_id: MOEX ID эмитента.
        issue_tree_id: treeId выпуска облигации.
        headers: HTTP-заголовки для запроса.

    Returns:
        Список значений ``moexWebsiteLink`` для целевых типов документов.
    """
    url = f"{_MOEX_DISCLOSURE_TREE_URL}/{emitent_id}/{issue_tree_id}"
    print(f"[MOEX STEP3] GET {url}")
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        print(f"[MOEX STEP3] HTTP {response.status_code}")
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException as exc:
        print(f"[MOEX STEP3] Ошибка запроса: {exc}")
        return []

    docs: List[Dict[str, Any]] = data.get("docs") or []
    print(f"[MOEX STEP3] Получено документов: {len(docs)}")
    links: List[str] = []
    for doc in docs:
        doc_type: str = doc.get("documentType") or ""
        link: Optional[str] = doc.get("moexWebsiteLink")
        if doc_type in _TARGET_DOC_TYPES:
            print(f"[MOEX STEP3]   Целевой документ: type='{doc_type}', link='{link}'")
            if link:
                links.append(link)
        else:
            print(f"[MOEX STEP3]   Пропущен: type='{doc_type}'")
    print(f"[MOEX STEP3] Итого ссылок для скачивания: {len(links)}")
    return links


def _download_docs(
    moex_links: List[str],
    headers: Dict[str, str],
) -> List[Tuple[str, bytes]]:
    """Скачивает PDF-документы по ссылкам MOEX.

    Args:
        moex_links: Список значений ``moexWebsiteLink``.
        headers: HTTP-заголовки для запроса.

    Returns:
        Список кортежей ``(filename, content)`` для успешно скачанных файлов.
    """
    download_headers: Dict[str, str] = {
        "User-Agent": headers.get("User-Agent", ""),
        "Accept": "*/*",
    }
    results: List[Tuple[str, bytes]] = []
    for moex_link in moex_links:
        filename: str = moex_link.split("/")[-1]
        file_url = f"{_MOEX_FILE_BASE_URL}/{moex_link}"
        print(f"[MOEX STEP4] Скачивание: GET {file_url}")
        try:
            response = requests.get(file_url, headers=download_headers, timeout=_TIMEOUT)
            print(f"[MOEX STEP4] HTTP {response.status_code}, Content-Length: {len(response.content)} байт")
            response.raise_for_status()
            results.append((filename, response.content))
            print(f"[MOEX STEP4] Успешно скачан: {filename}")
        except requests.RequestException as exc:
            print(f"[MOEX STEP4] Ошибка скачивания {filename}: {exc}")
            continue
    print(f"[MOEX STEP4] Итого скачано: {len(results)} из {len(moex_links)}")
    return results
