"""Утилиты для работы с e-disclosure.ru.

Предоставляет функции поиска компаний по ИНН и поиска событий по
регистрационному номеру облигации.
"""

import html
import io
import random
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin

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

# Параллельная загрузка HTML текстов событий только внутри одного года
# (:func:`fetch_emitent_year_events_unfiltered`); между годами и эмитентами — по-прежнему последовательно.
_EMITENT_EVENT_TEXT_MAX_WORKERS: int = 6
_EMITENT_EVENT_TEXT_JITTER_SEC: Tuple[float, float] = (0.05, 0.2)

# Заголовки событий, которые исключаются из пайплайна (не передаются в LLM).
_EXCLUDED_EVENT_TITLE = (
    "Перевод эмиссионных ценных бумаг эмитента из одного котировального списка "
    "в другой котировальный список"
)

_FILES_PAGE_URL = "https://www.e-disclosure.ru/portal/files.aspx"
_COMPANY_PORTAL_URL = "https://www.e-disclosure.ru/portal/company.aspx"

# Фраза-маркер, идентифицирующая документ «Решение о выпуске ценных бумаг»
_BOND_DECISION_PHRASE: str = "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ"

# Паттерн документа «Изменения в решение о выпуске» (шаги 2–3 не применяются).
_AMENDMENTS_PHRASE_PATTERN: re.Pattern[str] = re.compile(
    r"ИЗМЕНЕНИ[ЕЯ]\s+в\s+решение\s+о\s+выпуске",
    re.IGNORECASE,
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


def extract_bond_decision_data(text: str) -> str:
    """Извлекает структурированные данные из документа «Решение о выпуске ценных бумаг».

    Обрезает хвост документа начиная с раздела 9 («Сведения о представителе
    владельцев облигаций»), извлекает шапку (до «на основании решения») и
    нумерованные разделы, исключая разделы с пометкой «Не применимо».

    Args:
        text: Полный текст markdown-документа.

    Returns:
        Строка с шапкой и отфильтрованными разделами, разделёнными пустой строкой.
        Если шапка не найдена, возвращает только отфильтрованные разделы.
    """
    print(
        f"  [BOND_DECISION] extract: входной текст {len(text)} символов",
        flush=True,
    )

    clean_text: str = re.split(
        r"9\.\s+Сведения о представителе владельцев",
        text,
        flags=re.IGNORECASE,
    )[0]
    print(
        f"  [BOND_DECISION] extract: после обрезки раздела 9 — {len(clean_text)} символов",
        flush=True,
    )

    # Шапка: от «РЕШЕНИЕ О ВЫПУСКЕ» до «на основании решения» (гибкие пробелы/переносы)
    header_match: Optional[re.Match[str]] = re.search(
        r"(РЕШЕНИЕ О ВЫПУСКЕ.*?)(?=\s*на\s+основании\s+решения)",
        clean_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not header_match:
        # Fallback: до первого нумерованного раздела (1., 2. и т.д.)
        header_match = re.search(
            r"(РЕШЕНИЕ О ВЫПУСКЕ.*?)(?=^\s*\d+\.)",
            clean_text,
            re.DOTALL | re.IGNORECASE | re.MULTILINE,
        )
    header: str = header_match.group(1).strip() if header_match else ""
    print(
        f"  [BOND_DECISION] extract: шапка найдена={bool(header_match)}, длина={len(header)}",
        flush=True,
    )

    # Разделы: markdown-заголовки ## 1., ## 2., ## 4.1. и т.д. (формат PDF2MD)
    items: List[str] = re.findall(
        r"(^\s*##\s*\d+(?:\.\d+)*\.\s*(?:(?!Не применимо).)*?)(?=^\s*##\s*\d+(?:\.\d+)*\.|\Z)",
        clean_text,
        re.DOTALL | re.MULTILINE,
    )
    if not items:
        # Fallback: нумерация без ## (1., 2., 5.4.)
        items = re.findall(
            r"(^\s*\d+(?:\.\d+)*\.\s*(?:(?!Не применимо).)*?)(?=^\s*\d+(?:\.\d+)*\.|\Z)",
            clean_text,
            re.DOTALL | re.MULTILINE,
        )
    if not items:
        # Fallback: простой формат «1.» без подпунктов
        items = re.findall(
            r"(^\s*\d+\.\s*(?:(?!Не применимо).)*?)(?=^\s*\d+\.|\Z)",
            clean_text,
            re.DOTALL | re.MULTILINE,
        )
    filtered_items: List[str] = [i.strip() for i in items if i.strip()]
    print(
        f"  [BOND_DECISION] extract: найдено разделов={len(items)}, после фильтра={len(filtered_items)}",
        flush=True,
    )
    if not items and header_match is not None:
        # Разделы не найдены — показываем текст после шапки для отладки формата
        after_header: str = clean_text[header_match.end() : header_match.end() + 4000]
        snippet: str = after_header.replace("\n", "↵")
        print(
            f"  [BOND_DECISION] extract: текст после шапки (4000 символов): {snippet!r}",
            flush=True,
        )

    parts: List[str] = []
    if header:
        parts.append(header)
    parts.extend(filtered_items)

    result: str = "\n\n".join(parts)
    print(
        f"  [BOND_DECISION] extract: итоговая длина={len(result)} символов",
        flush=True,
    )
    if len(result) == 0:
        snippet: str = clean_text[:800].replace("\n", "↵")
        print(
            f"  [BOND_DECISION] extract: образец текста (первые 800 символов): {snippet!r}",
            flush=True,
        )
    return result


def process_markdown_if_bond_decision(content: str) -> str:
    """Проверяет наличие маркера решения о выпуске и применяет извлечение данных.

    Если в тексте обнаружена фраза ``_BOND_DECISION_PHRASE`` (без учёта регистра),
    возвращает результат :func:`extract_bond_decision_data`. Иначе — исходный текст.

    Args:
        content: Текст markdown-документа, полученного после конвертации PDF.

    Returns:
        Обработанный текст (если маркер найден) или исходный ``content``.
    """
    has_marker: bool = bool(re.search(_BOND_DECISION_PHRASE, content, re.IGNORECASE))
    print(
        f"  [BOND_DECISION] process: маркер «{_BOND_DECISION_PHRASE}» найден={has_marker}, вход={len(content)} символов",
        flush=True,
    )
    if has_marker:
        return extract_bond_decision_data(content)
    return content


def clean_markdown_after_pdf2md(content: str) -> str:
    """Очищает сырой markdown от pdf2md перед сохранением.

    Args:
        content: Сырой текст markdown-документа.

    Returns:
        Очищенный текст.
    """
    # Шаг 1: сначала очистка от мусора всего файла.
    content = content.replace("\u00a0", " ")
    content = re.sub(r"(\d+(?:\.\d+)*)\\.", r"\1.", content)
    content = content.replace("\\-", "-")
    content = content.replace("\\\n", "\n").replace("\\\r", "\r")
    content = re.sub(r"^\s*<!-- -->\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^\s*#+\s*$", "", content, flags=re.MULTILINE)

    # Шаг 2–3: поиск заголовков в очищенном тексте.
    is_amendments_doc: bool = bool(_AMENDMENTS_PHRASE_PATTERN.search(content))
    header_match: Optional[re.Match[str]] = (
        None if is_amendments_doc else re.search(_BOND_DECISION_PHRASE, content, re.IGNORECASE)
    )

    if header_match is not None:
        # Шаг 4: удалить текст до заголовка (сам заголовок оставить).
        content = content[header_match.start():]

        # Шаг 5: удалить блок от «Утверждено решением» до (не включая) «Вид, категория...».
        content = re.sub(
            r"Утверждено\s+решением.*?(?=Вид,\s*категория\s*\([^)]*\),?\s*ценных\s*бумаг)",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    return content


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


def _get_plain_session() -> requests.Session:
    """Возвращает сессию без bootstrap страницы поиска и без токена."""
    global _SESSION_CACHE

    if _SESSION_CACHE["session"] is not None:
        return _SESSION_CACHE["session"]

    session = requests.Session()
    session.headers.update(_API_HEADERS)
    _SESSION_CACHE["session"] = session
    print(
        "  [API] INIT plain session (without poisk-po-kompaniyam bootstrap)",
        flush=True,
    )
    return session


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


def clean_event_text(text: str) -> str:
    """Удаляет из текста события лишние блоки и маркеры для упрощения анализа LLM.

    Убирает пункт «1. Общие сведения» целиком, пункт «3. Подпись»,
    маркеры подпунктов (2.1., 2.2. и т.д.) в начале строк и заголовок «2. Содержание сообщения».
    Используется после отбора событий по фильтрам — для выделения нужной текстовой части
    перед сохранением в events.json (полный текст сохраняется отдельно, обработанный — в processed_text).

    Args:
        text: Исходный текст сообщения события.

    Returns:
        Очищенный текст (с удалёнными частями по регулярным выражениям).
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


def normalize_reg_number(reg_number: str) -> Tuple[str, str]:
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


def event_text_matches_reg_number(
    text: str,
    reg_num_ru: str,
    reg_num_lat: str,
) -> bool:
    """Проверяет, содержит ли текст события полный регистрационный номер.

    Учитываются только полные совпадения (кириллическая и латинская нормализации).

    Args:
        text: Текст события.
        reg_num_ru: Регистрационный номер в кириллической нормализации.
        reg_num_lat: Регистрационный номер в латинской нормализации.

    Returns:
        ``True``, если в тексте есть полный номер; иначе ``False``.
    """
    text_lower = text.lower()
    return (
        (reg_num_ru and reg_num_ru.lower() in text_lower)
        or (reg_num_lat and reg_num_lat.lower() in text_lower)
    )


def _find_all_events_sorted_by_date(
    events: List[Dict[str, Any]],
    date_obj: date,
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
    filtered: List[Tuple[date, Dict[str, Any]]] = []
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


def _find_all_events_sorted_by_date_include_all(
    events: List[Dict[str, Any]],
    date_obj: date,
) -> List[Dict[str, Any]]:
    """Как :func:`_find_all_events_sorted_by_date`, но **без** исключения заголовка ``_EXCLUDED_EVENT_TITLE``.

    Используется для выгрузки всех событий эмитента в JSON (пайплайн без фильтров по названию).

    Args:
        events: Список событий, полученных от API.
        date_obj: Граничная дата (события с этой датой и позже исключаются).

    Returns:
        Список событий, отсортированных по дате (от более поздних к более ранним).
    """
    filtered: List[Tuple[date, Dict[str, Any]]] = []
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
        Список словарей с полями ``event_name``, ``event_date`` (``None`` при ошибке),
        ``full_text`` (исходный текст события), ``text`` (текст после обработки регулярными
        выражениями — clean_event_text). В LLM передавать только ``text``.
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

    reg_num_ru, reg_num_lat = normalize_reg_number(reg_number)

    result: List[Dict[str, Optional[str]]] = []
    for event in sorted_events:
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        if event_text_matches_reg_number(text, reg_num_ru, reg_num_lat):
            full_text: str = text
            processed_text: str = clean_event_text(text)
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


def get_events_with_full_text(
    date: str,
    company_id: int,
) -> List[Dict[str, Any]]:
    """Загружает все события компании за год и возвращает те, у которых есть непустой текст.

    Не фильтрует по регистрационному номеру — возвращает все события с непустым текстом,
    отсортированные от новых к старым (строго раньше ``date``).

    Args:
        date: Граничная дата в формате YYYY-MM-DD. Включаются только события строго раньше неё.
        company_id: ID компании на e-disclosure.ru.

    Returns:
        Список словарей с полями ``event_name``, ``event_date``, ``full_text``, ``text``.
        Пустой список, если дата невалидна или событий с текстом не найдено.
    """
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        print(f"  [EVENTS ALL] Невалидная дата: {date!r} — возвращаем []", flush=True)
        return []

    year = date_obj.year
    print(
        f"  [EVENTS ALL] Загрузка всех событий: company_id={company_id}, year={year}",
        flush=True,
    )

    session, _ = _get_session()
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
    print(f"  [EVENTS ALL] Событий после фильтра: {len(sorted_events)}", flush=True)

    result: List[Dict[str, Any]] = []
    for event in sorted_events:
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        full_text: str = text
        processed_text: str = clean_event_text(text)
        event_date = _format_event_date(event.get("eventDate"))
        event_name: str = event.get("eventName") or ""
        result.append({
            "event_name": event_name,
            "event_date": event_date,
            "full_text": full_text,
            "text": processed_text,
        })

    print(f"  [EVENTS ALL] Событий с непустым текстом: {len(result)}", flush=True)
    return result


def get_events_with_full_text_for_year(
    company_id: int,
    year: int,
) -> List[Dict[str, Any]]:
    """Загружает все события компании за конкретный календарный год с полным текстом.

    В отличие от :func:`get_events_with_full_text`, **не** применяет фильтрацию
    по граничной дате — возвращает **все** события за запрошенный год
    (кроме ``_EXCLUDED_EVENT_TITLE``), отсортированные от новых к старым.

    Args:
        company_id: ID компании на e-disclosure.ru.
        year: Календарный год для параметра ``year`` в API.

    Returns:
        Список словарей с полями ``event_name``, ``event_date``, ``full_text``, ``text``.
        Пустой список, если событий с текстом нет.
    """
    # Far-future boundary to include ALL events without date filtering
    far_future: date = date(9999, 12, 31)

    print(
        f"  [EVENTS YEAR] Загрузка всех событий: company_id={company_id}, year={year}",
        flush=True,
    )

    session, _ = _get_session()
    params: Dict[str, Any] = {"companyId": company_id, "year": year}
    events_full_url: str = f"{_EVENTS_URL}?companyId={company_id}&year={year}"
    print(f"  [API] GET {events_full_url}", flush=True)
    response: requests.Response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    events: Any = response.json()

    sorted_events: List[Dict[str, Any]] = _find_all_events_sorted_by_date(events, far_future)
    print(f"  [EVENTS YEAR] Событий после фильтра: {len(sorted_events)}", flush=True)

    result: List[Dict[str, Any]] = []
    for event in sorted_events:
        pseudo_guid: Optional[str] = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        text: Optional[str] = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        full_text: str = text
        processed_text: str = clean_event_text(text)
        event_date: Optional[str] = _format_event_date(event.get("eventDate"))
        event_name: str = event.get("eventName") or ""
        result.append({
            "event_name": event_name,
            "event_date": event_date,
            "full_text": full_text,
            "text": processed_text,
        })

    print(f"  [EVENTS YEAR] Событий с непустым текстом: {len(result)}", flush=True)
    return result


def _fetch_emitent_event_text_worker(
    task: Tuple[int, str, Any, Any, str, Any, Any],
) -> Tuple[int, Optional[Dict[str, Optional[str]]]]:
    """Загружает полный текст одного события (потокобезопасно: своя Session и джиттер).

    Args:
        task: ``(индекс, pseudoGUID, eventDate, eventName,
               pseudoGUID_str, isCorrectedByAnotherEvent, fileIconName)``.

    Returns:
        Пара ``(index, словарь события или None если текста нет)``.
    """
    idx: int
    pseudo_guid: str
    event_date_raw: Any
    event_name_raw: Any
    pseudo_guid_str: str
    is_corrected_raw: Any
    file_icon_raw: Any
    idx, pseudo_guid, event_date_raw, event_name_raw, pseudo_guid_str, is_corrected_raw, file_icon_raw = task
    lo: float
    hi: float
    lo, hi = _EMITENT_EVENT_TEXT_JITTER_SEC
    time.sleep(random.uniform(lo, hi))
    session: requests.Session = _get_plain_session()
    text: Optional[str] = _extract_event_text(str(pseudo_guid), session)
    if not text:
        return (idx, None)
    event_date: str = _format_event_date(event_date_raw)
    event_name: str = str(event_name_raw or "")
    return (
        idx,
        {
            "event_name": event_name,
            "event_date": event_date,
            "full_text": text,
            "pseudoGUID": pseudo_guid_str,
            "is_corrected_by_another_event": bool(is_corrected_raw) if is_corrected_raw is not None else False,
            "file_icon_name": str(file_icon_raw) if file_icon_raw else None,
        },
    )


def fetch_emitent_year_events_unfiltered(
    *,
    company_id: int,
    api_year: int,
    boundary_date: str,
) -> List[Dict[str, Optional[str]]]:
    """Загружает события компании за календарный год ``api_year`` с полным текстом, без фильтра по заголовку.

    В запросе к API передаётся ``year=api_year`` (как на вкладках сайта). События фильтруются
    только по границе ``boundary_date`` (строго раньше этой даты), без исключения
    ``_EXCLUDED_EVENT_TITLE``.

    Тексты страниц событий (``event.aspx``) загружаются **параллельно только внутри этого года**:
    до ``_EMITENT_EVENT_TEXT_MAX_WORKERS`` потоков; перед каждым запросом — случайная пауза
    (джиттер) в диапазоне ``_EMITENT_EVENT_TEXT_JITTER_SEC`` секунд.

    Args:
        company_id: ID компании на e-disclosure.ru.
        api_year: Год для параметра ``year`` в ``/api/events/page``.
        boundary_date: Граничная дата YYYY-MM-DD (как в существующем пайплайне событий).

    Returns:
        Список словарей с ключами ``event_name``, ``event_date``, ``full_text``.
    """
    try:
        date_obj = datetime.strptime(boundary_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        print(
            f"  [EMITENT EVENTS] Невалидная граничная дата: {boundary_date!r} — []",
            flush=True,
        )
        return []

    print(
        f"  [EMITENT EVENTS] Год API={api_year}, граница={boundary_date}, company_id={company_id}",
        flush=True,
    )

    session = _get_plain_session()
    params = {"companyId": company_id, "year": api_year}
    events_full_url = f"{_EVENTS_URL}?companyId={company_id}&year={api_year}"
    print(f"  [API] GET {events_full_url}", flush=True)
    response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session = _get_plain_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    events = response.json()

    sorted_events = _find_all_events_sorted_by_date_include_all(events, date_obj)
    print(f"  [EMITENT EVENTS] Событий после фильтра по дате: {len(sorted_events)}", flush=True)

    indexed_tasks: List[Tuple[int, str, Any, Any, str, Any, Any]] = []
    for idx, event in enumerate(sorted_events):
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        indexed_tasks.append(
            (
                idx,
                str(pseudo_guid),
                event.get("eventDate"),
                event.get("eventName"),
                str(pseudo_guid),
                event.get("isCorrectedByAnotherEvent"),
                event.get("fileIconName"),
            ),
        )

    if not indexed_tasks:
        print(
            f"  [EMITENT EVENTS] Событий с непустым текстом: 0",
            flush=True,
        )
        return []

    workers: int = min(_EMITENT_EVENT_TEXT_MAX_WORKERS, len(indexed_tasks))
    print(
        f"  [EMITENT EVENTS] Параллельная загрузка текстов: workers={workers}, "
        f"jitter_sec={_EMITENT_EVENT_TEXT_JITTER_SEC}",
        flush=True,
    )

    result_by_idx: Dict[int, Dict[str, Optional[str]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx: Dict[Any, int] = {
            executor.submit(_fetch_emitent_event_text_worker, task): task[0]
            for task in indexed_tasks
        }
        for fut in as_completed(future_to_idx):
            idx_done: int
            payload: Optional[Dict[str, Optional[str]]]
            idx_done, payload = fut.result()
            if payload is not None:
                result_by_idx[idx_done] = payload

    result: List[Dict[str, Optional[str]]] = [
        result_by_idx[k] for k in sorted(result_by_idx.keys())
    ]

    print(f"  [EMITENT EVENTS] Событий с непустым текстом: {len(result)}", flush=True)
    return result


def fetch_events_page_json_only(company_id: int, api_year: int) -> List[Dict[str, Any]]:
    """Загружает сырой JSON списка событий с ``/api/events/page`` без загрузки текстов страниц.

    Args:
        company_id: ID компании на e-disclosure.ru.
        api_year: Параметр ``year`` в запросе.

    Returns:
        Список объектов событий из ответа API (как есть).
    """
    session: requests.Session = _get_plain_session()
    params: Dict[str, Any] = {"companyId": company_id, "year": api_year}
    url: str = f"{_EVENTS_URL}?companyId={company_id}&year={api_year}"
    print(f"  [API] GET (metadata only) {url}", flush=True)
    response: requests.Response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session = _get_plain_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    payload: Any = response.json()
    if not isinstance(payload, list):
        return []
    return payload


def _event_date_from_api_item(event: Dict[str, Any]) -> Optional[date]:
    """Возвращает дату события из поля ``eventDate`` ответа API (только дата, локально)."""
    event_date_str: Optional[str] = event.get("eventDate")
    if not event_date_str:
        return None
    try:
        return datetime.fromisoformat(
            str(event_date_str).replace("Z", "+00:00")
        ).date()
    except (ValueError, TypeError):
        return None


def find_latest_event_metadata_across_years(
    company_id: int,
    years: List[int],
    *,
    not_after: date,
) -> Optional[Tuple[date, str]]:
    """По сырым JSON за перечень лет находит событие с максимальной датой (не позже ``not_after``).

    Returns:
        ``(дата, pseudoGUID)`` или ``None``, если событий с датой нет.
    """
    best_date: Optional[date] = None
    best_guid: str = ""
    for y in years:
        raw: List[Dict[str, Any]] = fetch_events_page_json_only(company_id, y)
        for ev in raw:
            d: Optional[date] = _event_date_from_api_item(ev)
            if d is None or d > not_after:
                continue
            guid: str = str(ev.get("pseudoGUID") or "")
            if best_date is None or d > best_date or (d == best_date and guid > best_guid):
                best_date = d
                best_guid = guid
    if best_date is None:
        return None
    return (best_date, best_guid)


def parse_latest_event_from_emitent_file_payload(
    data: Dict[str, Any],
) -> Optional[Tuple[date, str, int]]:
    """Из сохранённого JSON эмитента (ключи — годы) находит последнее по дате событие.

    Returns:
        ``(event_date, pseudoGUID, calendar_year_of_event)`` или ``None``.
    """
    best: Optional[Tuple[date, str, int]] = None
    for year_key, events in data.items():
        if not isinstance(events, list):
            continue
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ds: Optional[str] = ev.get("event_date")
            if not ds or not str(ds).strip():
                continue
            try:
                d: date = datetime.strptime(str(ds)[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            guid: str = str(ev.get("pseudoGUID") or "")
            y_ev: int = d.year
            cand: Tuple[date, str, int] = (d, guid, y_ev)
            if best is None or cand[0] > best[0] or (
                cand[0] == best[0] and cand[1] > best[1]
            ):
                best = cand
    return best


def merge_emitent_event_lists(
    existing: List[Dict[str, Optional[str]]],
    new_items: List[Dict[str, Optional[str]]],
) -> List[Dict[str, Optional[str]]]:
    """Объединяет списки событий одного года, убирая дубликаты по (event_date, pseudoGUID)."""
    seen: Set[Tuple[str, str]] = set()
    merged: List[Dict[str, Optional[str]]] = []
    for ev in existing + new_items:
        key: Tuple[str, str] = (
            str(ev.get("event_date") or ""),
            str(ev.get("pseudoGUID") or ""),
        )
        if key in seen:
            continue
        if not key[0] and not key[1]:
            continue
        seen.add(key)
        merged.append(ev)

    def _sort_key(e: Dict[str, Optional[str]]) -> Tuple[date, str]:
        ds: Optional[str] = e.get("event_date")
        nm: str = str(e.get("event_name") or "")
        if not ds:
            return (date.min, nm)
        try:
            return (datetime.strptime(str(ds)[:10], "%Y-%m-%d").date(), nm)
        except ValueError:
            return (date.min, nm)

    merged.sort(key=_sort_key, reverse=True)
    return merged


def _company_portal_html_needs_browser(html: str) -> bool:
    """Эвристика: HTML — заглушка JS/бот, нужен браузер (Playwright)."""
    h = html.lower()
    if "data-event-year" in h:
        return False
    if "forbidden" in h and "not a bot" in h:
        return True
    if "id_spinner" in h or "servicepipe" in h:
        return True
    if len(html) < 4000 and "tabs-control" not in h:
        return True
    return False


def _fetch_company_portal_html_playwright(page_url: str) -> str:
    """Загружает страницу компании через Chromium (обход JS-защиты)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Страница e-disclosure не содержит разметки вкладок годов; "
            "установите пакет playwright и выполните playwright install chromium."
        ) from exc

    print(f"  [COMPANY PAGE] Playwright GET {page_url}", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=_HTML_HEADERS.get("User-Agent", ""),
                locale="ru-RU",
            )
            page = context.new_page()
            page.goto(page_url, wait_until="load", timeout=120000)
            time.sleep(2.0)
            content: str = page.content()
        finally:
            browser.close()
    return content


def fetch_company_portal_html(company_id: int) -> str:
    """Загружает HTML страницы ``company.aspx`` (вкладки годов событий)."""
    page_url = f"{_COMPANY_PORTAL_URL}?id={company_id}"
    session = _get_plain_session()
    print(f"  [COMPANY PAGE] GET {page_url}", flush=True)
    response = session.get(page_url, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session = _get_plain_session()
        response = session.get(page_url, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    response.raise_for_status()
    text: str = response.text
    if _company_portal_html_needs_browser(text):
        text = _fetch_company_portal_html_playwright(page_url)
    return text


def _parse_events_years_hidden(html: str) -> Optional[List[int]]:
    """Извлекает годы из скрытого поля ``<input id="EventsYears" value="...">``.

    Returns:
        Отсортированный по возрастанию список уникальных годов, либо ``None``,
        если поле не найдено или из ``value`` не удалось получить ни одного года.
    """
    from html import unescape as _html_unescape

    for tag_m in re.finditer(r"<input\b[^>]+>", html, re.IGNORECASE):
        tag: str = tag_m.group(0)
        if not re.search(r'\bid\s*=\s*["\']EventsYears["\']', tag, re.IGNORECASE):
            continue
        vm = re.search(r'\bvalue\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
        if not vm:
            return None
        raw: str = _html_unescape(vm.group(1).strip())
        if not raw:
            return None
        out: List[int] = []
        for part in raw.split(","):
            p = part.strip()
            if not p:
                continue
            try:
                out.append(int(p))
            except ValueError:
                continue
        if not out:
            return None
        return sorted(set(out))
    return None


def list_company_portal_event_years(company_id: int) -> List[int]:
    """Возвращает список календарных годов событий со страницы компании.

    Один запрос :func:`fetch_company_portal_html`. Годы берутся **только** из скрытого
    поля ``<input id="EventsYears" value="...">``.

    Returns:
        Уникальные годы по возрастанию.

    Raises:
        ValueError: Поле ``EventsYears`` отсутствует, пустое или не удалось разобрать годы.
    """
    page_html: str = fetch_company_portal_html(company_id)
    hidden_years: Optional[List[int]] = _parse_events_years_hidden(page_html)
    if hidden_years is None:
        raise ValueError(
            "На странице компании не найдено скрытое поле EventsYears с перечнем годов "
            "(id=EventsYears) или value пустой/некорректен. Проверьте company_id и HTML страницы."
        )
    print(
        f"  [COMPANY PAGE] EventsYears (hidden): count={len(hidden_years)}, years={hidden_years}",
        flush=True,
    )
    return hidden_years


def resolve_company_portal_earliest_event_year(company_id: int) -> int:
    """Совместимость: минимальный год из :func:`list_company_portal_event_years`.

    Args:
        company_id: ID компании на e-disclosure.ru.

    Returns:
        Самый ранний год из списка годов портала.

    Raises:
        ValueError: Не удалось определить годы (см. :func:`list_company_portal_event_years`).
    """
    years: List[int] = list_company_portal_event_years(company_id)
    earliest: int = min(years)
    print(
        f"  [COMPANY PAGE] Начальный год (compat, min): {earliest}",
        flush=True,
    )
    return earliest


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
