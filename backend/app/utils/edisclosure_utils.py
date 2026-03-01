"""Утилиты для работы с e-disclosure.ru.

Предоставляет функции поиска компаний по ИНН и поиска событий по
регистрационному номеру облигации.
"""

import html
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin

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

# Заголовки событий, которые исключаются из пайплайна (не передаются в LLM).
_EXCLUDED_EVENT_TITLE = (
    "Перевод эмиссионных ценных бумаг эмитента из одного котировального списка "
    "в другой котировальный список"
)

_FILES_PAGE_URL = "https://www.e-disclosure.ru/portal/files.aspx"

_MOEX_DISCLOSURE_TREE_URL = "https://web.moex.com/moex-web-icdb-api/api/v1/bond-disclosure-tree/reporting"
_MOEX_FILE_BASE_URL = "https://fs.moex.com/emidocs"

_TARGET_DOC_TYPES = (
    "Решение о выпуске (дополнительном выпуске) ценных бумаг",
    "Документ, содержащий условия размещения ценных бумаг",
    "Условия выпуска облигаций",
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
    print(f"  [API] GET {_SEARCH_PAGE_URL}", flush=True)
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
    _clear_session_cache()
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

    print(f"  [API] POST {_URL}", flush=True)
    response = session.post(_URL, data=data, timeout=_TIMEOUT)

    if response.status_code == 403:
        _clear_session_cache()
        session, token = _get_session()
        data["__RequestVerificationToken"] = token
        response = session.post(_URL, data=data, timeout=_TIMEOUT)

    response.raise_for_status()
    payload = response.json()

    found_list = payload.get("foundCompaniesList") or []

    result: List[Dict[str, Any]] = []
    for item in found_list:
        result.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "district": item.get("district"),
            "region": item.get("region"),
            "branch": item.get("branch"),
        })

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


def _clean_event_text(text: str) -> str:
    """Удаляет из текста события лишние блоки и маркеры для упрощения анализа LLM.

    Убирает пункт «1. Общие сведения» целиком, пункт «3. Подпись»,
    маркеры подпунктов (2.1., 2.2. и т.д.) в начале строк и заголовок «2. Содержание сообщения».

    Args:
        text: Исходный текст сообщения события.

    Returns:
        Очищенный текст.
    """
    # 1. Удаляем "Общие сведения" (пункт 1) целиком
    text = re.sub(
        r"1\. Общие сведения.*?2\. Содержание сообщения",
        "",
        text,
        flags=re.DOTALL,
    )
    # 2. Удаляем "Подпись" (пункт 3)
    text = re.sub(r"3\. Подпись.*", "", text, flags=re.DOTALL)
    # 3. Удаляем маркеры подпунктов (2.1., 2.2. и т.д.) в начале строк
    text = re.sub(r"^\d+\.\d+\.\s*", "", text, flags=re.MULTILINE)
    # 4. Удаляем заголовок раздела
    text = text.replace("2. Содержание сообщения", "")
    return text.strip()


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
    ``<порядковый_номер>-<код_эмитента>-<номер_программы>``.

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
        pattern2 = f"{serial_num}-{emitent_code}-{program_num}"
        if pattern2.lower() in text_lower:
            return True

    return False


def _find_all_events_sorted_by_date(
    events: List[Dict[str, Any]],
    date_obj: datetime.date,
) -> List[Dict[str, Any]]:
    """Возвращает все события строго раньше ``date_obj``, отсортированные от новых к старым.

    Исключает события с заголовком «Перевод эмиссионных ценных бумаг эмитента из одного
    котировального списка в другой котировальный список» — они не попадают в пайплайн.

    Args:
        events: Список событий, полученных от API.
        date_obj: Граничная дата (события с этой датой и позже исключаются).

    Returns:
        Список событий, отсортированных по дате (от более поздних к более ранним).
    """
    filtered: List[Tuple[datetime.date, Dict[str, Any]]] = []
    for event in events:
        event_name = (event.get("eventName") or "").strip()
        if event_name == _EXCLUDED_EVENT_TITLE:
            continue
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
        Список словарей с полями ``event_name``, ``event_date`` (``None`` при ошибке),
        ``full_text`` (исходный текст события), ``text`` (текст после обработки регулярными
        выражениями — _clean_event_text). В LLM передавать только ``text``.
        Пустой список, если ``reg_number`` пустой или совпадений не найдено.
    """
    if not reg_number.strip():
        return []

    session, _ = _get_session()

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    year = date_obj.year

    params = {"companyId": company_id, "year": year}
    events_full_url = f"{_EVENTS_URL}?companyId={company_id}&year={year}"
    print(f"  [API] GET {events_full_url}", flush=True)
    response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    events = response.json()

    sorted_events = _find_all_events_sorted_by_date(events, date_obj)

    reg_num_ru, reg_num_lat = _normalize_reg_number(reg_number)
    parts_ru: Optional[Tuple[str, str, str]] = _parse_reg_number_parts(reg_num_ru)
    parts_lat: Optional[Tuple[str, str, str]] = _parse_reg_number_parts(reg_num_lat)

    result: List[Dict[str, Optional[str]]] = []
    for event in sorted_events:
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        if _event_text_matches_reg_number(text, reg_num_ru, reg_num_lat, parts_ru, parts_lat):
            full_text: str = text
            processed_text: str = _clean_event_text(text)
            event_date = _format_event_date(event.get("eventDate"))
            event_name = event.get("eventName") or ""
            event_url = f"{_EVENT_PAGE_URL}?EventId={pseudo_guid}"
            print(f"  [событие] {event_name} ({event_date}) → {event_url}", flush=True)
            result.append({
                "event_name": event_name,
                "event_date": event_date,
                "full_text": full_text,
                "text": processed_text,
            })

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
    reg_num_ru, reg_num_lat = _normalize_reg_number(reg_number)

    parts_ru = _parse_reg_number_parts(reg_num_ru)
    parts_lat = _parse_reg_number_parts(reg_num_lat)

    search_patterns: List[Tuple[str, str, str]] = []
    for parts, reg_num in ((parts_ru, reg_num_ru), (parts_lat, reg_num_lat)):
        if parts is not None:
            serial_num, emitent_code, program_num = parts
            program_pattern: str = f"{emitent_code}-{program_num}"
            search_patterns.append((program_pattern, reg_num, serial_num))

    if not search_patterns:
        return []

    moex_headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    program_tree_ids = _find_program_tree_ids(emitent_id, search_patterns, moex_headers)
    if not program_tree_ids:
        print("  [MOEX] Программа выпуска в дереве раскрытия не найдена", flush=True)
        return []

    target_links: List[str] = []
    for program_tree_id in program_tree_ids:
        issue_tree_id = _find_issue_tree_id(emitent_id, program_tree_id, search_patterns, moex_headers)
        if issue_tree_id is None:
            continue
        links = _find_doc_links(emitent_id, issue_tree_id, moex_headers)
        for link in links:
            if link not in target_links:
                target_links.append(link)

    if not target_links:
        print("  [MOEX] Документы для скачивания не найдены (дерево раскрытия)", flush=True)
        return []

    print(f"  [MOEX] Найдено документов для скачивания: {len(target_links)}", flush=True)
    for i, link in enumerate(target_links, start=1):
        full_url = f"{_MOEX_FILE_BASE_URL}/{link}"
        print(f"  [MOEX] Ссылка {i}: GET {full_url}", flush=True)
    return _download_docs(target_links, moex_headers)


def _find_program_tree_ids(
    emitent_id: int,
    search_patterns: List[Tuple[str, str, str]],
    headers: Dict[str, str],
) -> List[str]:
    """Ищет все treeId программ выпуска в дереве раскрытия MOEX, совпадающие с паттернами.

    Args:
        emitent_id: MOEX ID эмитента.
        search_patterns: Список троек ``(program_pattern, full_reg_num, serial_num)``.
        headers: HTTP-заголовки для запроса.

    Returns:
        Список treeId всех программ, у которых treeDisplayAdditional совпал с паттерном.
    """
    url = f"{_MOEX_DISCLOSURE_TREE_URL}/{emitent_id}"
    print(f"  [API] GET {url}", flush=True)
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException:
        return []

    nodes: List[Dict[str, Any]] = data.get("nodes") or []
    result: List[str] = []
    seen: set[str] = set()
    for node in nodes:
        tree_id = node.get("treeId")
        if tree_id is None or tree_id in seen:
            continue
        display: str = (node.get("treeDisplayAdditional") or "").lower()
        for program_pattern, _, _ in search_patterns:
            if program_pattern.lower() in display:
                result.append(tree_id)
                seen.add(tree_id)
                break
    return result


def _find_issue_tree_id(
    emitent_id: int,
    program_tree_id: str,
    search_patterns: List[Tuple[str, str, str]],
    headers: Dict[str, str],
) -> Optional[str]:
    """Ищет treeId конкретного выпуска облигации внутри программы.

    Выпуск считается найденным, если в treeDisplayAdditional выполняется
    хотя бы одно условие: полный рег. номер или паттерн
    «порядковый_номер-код_эмитента-номер_программы».

    Args:
        emitent_id: MOEX ID эмитента.
        program_tree_id: treeId программы выпуска.
        search_patterns: Список троек ``(program_pattern, full_reg_num, serial_num)``.
        headers: HTTP-заголовки для запроса.

    Returns:
        treeId выпуска или ``None``, если совпадение не найдено.
    """
    url = f"{_MOEX_DISCLOSURE_TREE_URL}/{emitent_id}/{program_tree_id}"
    print(f"  [API] GET {url}", flush=True)
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException:
        return None

    nodes: List[Dict[str, Any]] = data.get("nodes") or []
    for node in nodes:
        display: str = (node.get("treeDisplayAdditional") or "").lower()
        for program_pattern, full_reg_num, serial_num in search_patterns:
            if full_reg_num.lower() in display:
                return node.get("treeId")
            issue_pattern: str = f"{serial_num}-{program_pattern}"
            if issue_pattern.lower() in display:
                return node.get("treeId")
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
    print(f"  [API] GET {url}", flush=True)
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException:
        return []

    docs: List[Dict[str, Any]] = data.get("docs") or []
    links: List[str] = []
    for doc in docs:
        doc_type: str = doc.get("documentType") or ""
        link: Optional[str] = doc.get("moexWebsiteLink")
        if doc_type in _TARGET_DOC_TYPES and link:
            links.append(link)
    return links


def fetch_emission_documents_page(edisclosure_id: int) -> str:
    """Загружает HTML-страницу эмиссионных документов эмитента с e-disclosure.ru.

    Args:
        edisclosure_id: ID компании на сайте e-disclosure.ru.

    Returns:
        HTML-код страницы в виде строки.
    """
    url: str = f"{_FILES_PAGE_URL}?id={edisclosure_id}&type=7"
    print(f"  [API] GET {url}", flush=True)
    session, _ = _get_session()
    response: requests.Response = session.get(url, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(url, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.text


def _resolve_emission_file_url(url: str) -> str:
    """Преобразует относительный URL файла e-disclosure в абсолютный."""
    u: str = (url or "").strip()
    if not u:
        return u
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return urljoin(_MAIN_PAGE_URL + "/", u.lstrip("/"))


def download_emission_file(file_url: str) -> Optional[bytes]:
    """Скачивает файл по ссылке с e-disclosure.ru (страница эмиссионных документов).

    Поддерживает относительные URL (дополняет базой _MAIN_PAGE_URL).
    Использует ту же сессию и заголовки, что и для HTML-страниц.

    Args:
        file_url: Прямая ссылка на файл (из emission_documents.file_url).

    Returns:
        Содержимое файла в байтах или None при ошибке.
    """
    resolved: str = _resolve_emission_file_url(file_url)
    if not resolved:
        return None
    print(f"  [E-DISCLOSURE FILE] GET {resolved[:80]}...", flush=True)
    session, _ = _get_session()
    try:
        response: requests.Response = session.get(
            resolved, headers=_HTML_HEADERS, timeout=_TIMEOUT
        )
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"  [E-DISCLOSURE FILE] Ошибка загрузки: {e}", flush=True)
        return None


def extract_zip_to_dir(content: bytes, extract_dir: Path) -> List[str]:
    """Извлекает содержимое ZIP-архива в директорию с корректной кодировкой имён.

    Имена в архивах e-disclosure хранятся в CP866 (DOS/OEM кириллица). Параметр
    ZipFile(..., metadata_encoding="cp866") задаёт эту кодировку для полей имён
    в ZIP, поэтому namelist() возвращает уже правильные строки без перекодировки.

    Возвращаются имена всех извлечённых файлов (PDF, Word и др.).

    Args:
        content: Байты ZIP-архива.
        extract_dir: Директория для извлечения (например, backend/app/data/{secid}).

    Returns:
        Список имён всех извлечённых файлов, записанных в extract_dir (базовые имена).
    """
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    result: List[str] = []
    try:
        # cp866 — стандартная кириллическая кодировка DOS/OEM в архивах e-disclosure
        with zipfile.ZipFile(io.BytesIO(content), "r", metadata_encoding="cp866") as zf:
            for name in zf.namelist():
                if name.endswith("/") or ".." in name:
                    continue
                base_name: str = Path(name).name
                if not base_name:
                    continue
                target_path: Path = extract_dir / base_name
                if target_path.exists():
                    stem: str = target_path.stem
                    suffix: str = target_path.suffix
                    idx: int = 1
                    while target_path.exists():
                        base_name = f"{stem}_{idx}{suffix}"
                        target_path = extract_dir / base_name
                        idx += 1
                try:
                    with zf.open(name, "r") as src:
                        target_path.write_bytes(src.read())
                except (zipfile.BadZipFile, OSError) as e:
                    print(f"  [ZIP] Ошибка извлечения {name}: {e}", flush=True)
                    continue
                result.append(base_name)
    except zipfile.BadZipFile as e:
        print(f"  [ZIP] Невалидный архив: {e}", flush=True)
    return result


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
    for idx, moex_link in enumerate(moex_links, start=1):
        filename: str = moex_link.split("/")[-1]
        encoded_link: str = quote(moex_link, safe="/")
        file_url: str = f"{_MOEX_FILE_BASE_URL}/{encoded_link}"
        print(f"  [MOEX PDF] Запрос {idx}/{len(moex_links)}: GET {file_url}", flush=True)
        print(f"  [файл] {filename} → {file_url}", flush=True)
        try:
            response = requests.get(file_url, headers=download_headers, timeout=_TIMEOUT)
            response.raise_for_status()
            results.append((filename, response.content))
            print(f"  [файл] скачан: {filename} ({len(response.content)} байт)", flush=True)
        except requests.RequestException as e:
            print(f"  [файл] ошибка {filename}: {e}", flush=True)
            continue
    return results
