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

# Заголовки событий, которые исключаются из пайплайна (не передаются в LLM).
_EXCLUDED_EVENT_TITLE = (
    "Перевод эмиссионных ценных бумаг эмитента из одного котировального списка "
    "в другой котировальный список"
)

_FILES_PAGE_URL = "https://www.e-disclosure.ru/portal/files.aspx"

# Фраза-маркер, идентифицирующая документ «Решение о выпуске ценных бумаг»
_BOND_DECISION_PHRASE: str = "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ"

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
    """Очищает сырой markdown, полученный от сервиса pdf2md, перед сохранением на диск.

    Шаги выполняются строго по порядку:

    1. Проверяет наличие заголовка «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ» (без учёта регистра).
    2. Если заголовок найден — удаляет весь текст от начала файла до этого заголовка
       (сам заголовок сохраняется).
    3. Если заголовок найден — удаляет блок «Утверждено решением» до (не включая) строки
       «Вид, категория (тип), ценных бумаг»; вариант «(тип)» разрешает любое содержимое в скобках.
    4. Удаляет все символы неразрывного пробела (U+00A0) вне зависимости от наличия заголовка.

    Args:
        content: Сырой текст markdown-документа.

    Returns:
        Очищенный текст.
    """
    has_header: bool = bool(re.search(_BOND_DECISION_PHRASE, content, re.IGNORECASE))

    if has_header:
        # Шаг 2: удалить текст до заголовка (сам заголовок оставить).
        header_match: Optional[re.Match[str]] = re.search(
            _BOND_DECISION_PHRASE, content, re.IGNORECASE
        )
        if header_match:
            content = content[header_match.start():]

        # Шаг 3: удалить блок от «Утверждено решением» до (не включая) «Вид, категория...».
        content = re.sub(
            r"Утверждено\s+решением.*?(?=Вид,\s*категория\s*\([^)]*\),?\s*ценных\s*бумаг)",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Шаг 4: удалить неразрывные пробелы (U+00A0) — всегда.
    content = content.replace("\u00a0", " ")

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
