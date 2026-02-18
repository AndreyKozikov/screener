"""Утилита для поиска компаний по ИНН на e-disclosure.ru."""

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
_TARGET_EVENT_NAME = "Начисленные доходы по эмиссионным ценным бумагам эмитента"
_PLACEMENT_START_EVENT_NAME = "Дата начала размещения ценных бумаг"
_SEARCH_PAGE_URL = "https://www.e-disclosure.ru/poisk-po-kompaniyam"
_MAIN_PAGE_URL = "https://www.e-disclosure.ru"
_TIMEOUT = 30  # Увеличен таймаут для медленных соединений


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
    # Очищаем кэш перед каждым поиском компании
    _clear_session_cache()
    
    session, token = _get_session()

    # Формируем data, токен добавляем ПОСЛЕДНИМ (порядок может быть важен)
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

    response = session.post(_URL, data=data, timeout=_TIMEOUT)
    
    # Если получили 403, очищаем кэш и получаем новую сессию
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

    for company in result:
        print(company)

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


def _find_events_sorted_by_date(
    events: List[Dict[str, Any]],
    event_name: str,
    date_obj: datetime.date,
) -> List[Dict[str, Any]]:
    """Находит все события с указанным именем, не позже указанной даты, отсортированные по дате (от более поздних к более ранним).
    
    Args:
        events: Список событий.
        event_name: Название события для поиска.
        date_obj: Дата для сравнения.
    
    Returns:
        Список событий, отсортированных по дате (от более поздних к более ранним).
    """
    filtered = []
    for event in events:
        if event.get("eventName") != event_name:
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
    
    # Сортируем по дате (от более поздних к более ранним)
    filtered.sort(key=lambda x: x[0], reverse=True)
    
    return [event for _, event in filtered]


def get_accrued_income_event_text(
    date: str = "2025-04-24",
    company_id: int = 1480,
) -> List[Dict[str, str]]:
    """Извлекает тексты событий для компании до указанной даты.

    Ищет события:
    - «Начисленные доходы по эмиссионным ценным ценным бумагам эмитента»
    - «Дата начала размещения ценных бумаг»

    Для каждого типа события берёт первое подходящее (с eventDate не позже указанной даты),
    начиная с наиболее близкой к указанной дате.

    Args:
        date: Дата в формате YYYY-MM-DD. По умолчанию 2025-04-24.
        company_id: ID компании на e-disclosure. По умолчанию 1480.

    Returns:
        Список словарей с полями "event_name" и "text" для каждого найденного события.
    """
    session, _ = _get_session()

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    year = date_obj.year

    params = {"companyId": company_id, "year": year}
    response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    
    # Если получили 403, очищаем кэш и получаем новую сессию
    if response.status_code == 403:
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    
    response.raise_for_status()
    events = response.json()

    result: List[Dict[str, str]] = []

    # Ищем событие "Начисленные доходы по эмиссионным ценным бумагам эмитента"
    accrued_events = _find_events_sorted_by_date(events, _TARGET_EVENT_NAME, date_obj)
    for event in accrued_events:
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        
        result.append({
            "event_name": _TARGET_EVENT_NAME,
            "text": text,
        })
        print(f"Найдено событие: {_TARGET_EVENT_NAME}")
        print(text)
        break

    # Ищем событие "Дата начала размещения ценных бумаг"
    placement_events = _find_events_sorted_by_date(events, _PLACEMENT_START_EVENT_NAME, date_obj)
    for event in placement_events:
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        
        result.append({
            "event_name": _PLACEMENT_START_EVENT_NAME,
            "text": text,
        })
        print(f"Найдено событие: {_PLACEMENT_START_EVENT_NAME}")
        print(text)
        break

    return result
