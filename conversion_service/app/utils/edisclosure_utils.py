"""Утилиты для работы с e-disclosure.ru.

Предоставляет функции поиска компаний по ИНН и поиска событий по
регистрационному номеру облигации.
"""

import hashlib
import html
import io
import random
import re
import time
import zipfile
import rarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, unquote

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
_COMPANY_PORTAL_URL = "https://www.e-disclosure.ru/portal/company.aspx"
_MAIN_PAGE_URL = "https://www.e-disclosure.ru"
_TIMEOUT = 30

# Параллельная загрузка HTML текстов событий только внутри одного года
_EMITENT_EVENT_TEXT_MAX_WORKERS: int = 6
_EMITENT_EVENT_TEXT_JITTER_SEC: Tuple[float, float] = (0.05, 0.2)

_BOND_DECISION_PHRASE: str = "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ"
_AMENDMENTS_PHRASE_PATTERN: re.Pattern[str] = re.compile(
    r"ИЗМЕНЕНИ[ЕЯ]\s+в\s+решение\s+о\s+выпуске",
    re.IGNORECASE,
)


def _get_session_data() -> Tuple[requests.Session, str]:
    """Получает сессию и токен через requests."""
    session = requests.Session()
    session.headers.update(_API_HEADERS)
    
    print(f"  [API] GET {_SEARCH_PAGE_URL}", flush=True)
    response = session.get(_SEARCH_PAGE_URL, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    response.raise_for_status()
    
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
    """Ищет компанию по ИНН на e-disclosure.ru и возвращает id, name.

    Args:
        inn: ИНН компании (например, 7712040126).

    Returns:
        Список словарей с полями: id, name для каждой найденной компании.
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
        "__RequestVerificationToken": token,
    }

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


def _find_all_events_sorted_by_date_include_all(
    events: List[Dict[str, Any]],
    date_obj: date,
) -> List[Dict[str, Any]]:
    """Возвращает все события строго раньше ``date_obj``, отсортированные от новых к старым.

    Используется для выгрузки всех событий эмитента в JSON.

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


def _fetch_emitent_event_text_worker(
    task: Tuple[int, str, Any, Any, str, Any, Any],
) -> Tuple[int, Optional[Dict[str, Optional[str]]]]:
    """Загружает полный текст одного события (потокобезопасно: своя Session и джиттер)."""
    idx, pseudo_guid, event_date_raw, event_name_raw, pseudo_guid_str, is_corrected_raw, file_icon_raw = task
    lo, hi = _EMITENT_EVENT_TEXT_JITTER_SEC
    time.sleep(random.uniform(lo, hi))
    session = _get_plain_session()
    text = _extract_event_text(str(pseudo_guid), session)
    if not text:
        return (idx, None)
    event_date = _format_event_date(event_date_raw)
    event_name = str(event_name_raw or "")
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
    """Загружает события компании за календарный год ``api_year`` с полным текстом.

    Args:
        company_id: ID компании на e-disclosure.ru.
        api_year: Год для параметра ``year`` в ``/api/events/page``.
        boundary_date: Граничная дата YYYY-MM-DD.

    Returns:
        Список словарей с ключами ``event_name``, ``event_date``, ``full_text``.
    """
    try:
        date_obj = datetime.strptime(boundary_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        print(f"  [EMITENT EVENTS] Невалидная граничная дата: {boundary_date!r} — []", flush=True)
        return []

    print(f"  [EMITENT EVENTS] Год API={api_year}, граница={boundary_date}, company_id={company_id}", flush=True)

    session = _get_plain_session()
    params = {"companyId": company_id, "year": api_year}
    url = f"{_EVENTS_URL}?companyId={company_id}&year={api_year}"
    print(f"  [API] GET {url}", flush=True)
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
        print(f"  [EMITENT EVENTS] Событий с непустым текстом: 0", flush=True)
        return []

    workers: int = min(_EMITENT_EVENT_TEXT_MAX_WORKERS, len(indexed_tasks))
    print(f"  [EMITENT EVENTS] Параллельная загрузка текстов: workers={workers}", flush=True)

    result_by_idx: Dict[int, Dict[str, Optional[str]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {
            executor.submit(_fetch_emitent_event_text_worker, task): task[0]
            for task in indexed_tasks
        }
        for fut in as_completed(future_to_idx):
            idx_done, payload = fut.result()
            if payload is not None:
                result_by_idx[idx_done] = payload

    result: List[Dict[str, Optional[str]]] = [
        result_by_idx[k] for k in sorted(result_by_idx.keys())
    ]

    print(f"  [EMITENT EVENTS] Событий с непустым текстом: {len(result)}", flush=True)
    return result


def fetch_events_page_json_only(company_id: int, api_year: int) -> List[Dict[str, Any]]:
    """Загружает сырой JSON списка событий без загрузки текстов страниц."""
    session = _get_plain_session()
    params = {"companyId": company_id, "year": api_year}
    url = f"{_EVENTS_URL}?companyId={company_id}&year={api_year}"
    print(f"  [API] GET (metadata only) {url}", flush=True)
    response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session = _get_plain_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _event_date_from_api_item(event: Dict[str, Any]) -> Optional[date]:
    """Возвращает дату события из поля eventDate ответа API."""
    event_date_str = event.get("eventDate")
    if not event_date_str:
        return None
    try:
        return datetime.fromisoformat(str(event_date_str).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def find_latest_event_metadata_across_years(
    company_id: int,
    years: List[int],
    *,
    not_after: date,
) -> Optional[Tuple[date, str]]:
    """По сырым JSON за перечень лет находит событие с максимальной датой."""
    best_date: Optional[date] = None
    best_guid: str = ""
    for y in years:
        raw = fetch_events_page_json_only(company_id, y)
        for ev in raw:
            d = _event_date_from_api_item(ev)
            if d is None or d > not_after:
                continue
            guid = str(ev.get("pseudoGUID") or "")
            if best_date is None or d > best_date or (d == best_date and guid > best_guid):
                best_date = d
                best_guid = guid
    return (best_date, best_guid) if best_date else None


def list_company_portal_event_years(company_id: int) -> List[int]:
    """Возвращает список календарных годов событий со страницы компании."""
    page_url = f"{_COMPANY_PORTAL_URL}?id={company_id}"
    session = _get_plain_session()
    print(f"  [COMPANY PAGE] GET {page_url}", flush=True)
    response = session.get(page_url, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session = _get_plain_session()
        response = session.get(page_url, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    response.raise_for_status()
    html_content = response.text
    
    for tag_m in re.finditer(r"<input\b[^>]+>", html_content, re.IGNORECASE):
        tag = tag_m.group(0)
        if not re.search(r'\bid\s*=\s*["\']EventsYears["\']', tag, re.IGNORECASE):
            continue
        vm = re.search(r'\bvalue\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
        if not vm:
            return []
        raw = html.unescape(vm.group(1).strip())
        if not raw:
            return []
        out: List[int] = []
        for part in raw.split(","):
            try:
                out.append(int(part.strip()))
            except ValueError:
                continue
        print(f"  [COMPANY PAGE] EventsYears (hidden): count={len(out)}, years={sorted(set(out))}", flush=True)
        return sorted(set(out))
    return []


def merge_emitent_event_lists(
    existing: List[Dict[str, Optional[str]]],
    new_items: List[Dict[str, Optional[str]]],
) -> List[Dict[str, Optional[str]]]:
    """Объединяет списки событий одного года, убирая дубликаты."""
    seen: Set[Tuple[str, str]] = set()
    merged: List[Dict[str, Optional[str]]] = []
    for ev in existing + new_items:
        key = (str(ev.get("event_date") or ""), str(ev.get("pseudoGUID") or ""))
        if key in seen or (not key[0] and not key[1]):
            continue
        seen.add(key)
        merged.append(ev)

    def _sort_key(e):
        ds = e.get("event_date")
        try:
            return (datetime.strptime(str(ds)[:10], "%Y-%m-%d").date(), str(e.get("event_name") or ""))
        except (ValueError, TypeError):
            return (date.min, str(e.get("event_name") or ""))

    merged.sort(key=_sort_key, reverse=True)
    return merged


def _resolve_emission_file_url(url: str) -> str:
    """Преобразует относительный URL файла e-disclosure в абсолютный."""
    u = (url or "").strip()
    if not u or u.startswith(("http://", "https://")):
        return u
    return urljoin(_MAIN_PAGE_URL + "/", u.lstrip("/"))


def download_emission_file(file_url: str, referer: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """Скачивает файл по ссылке с e-disclosure.ru.
    
    Returns:
        Кортеж (содержимое_файла, имя_файла_из_заголовков).
    """
    resolved = _resolve_emission_file_url(file_url)
    if not resolved:
        return None, None
    
    print(f"  [E-DISCLOSURE FILE] GET {resolved[:80]}...", flush=True)
    session, _ = _get_session()
    
    headers = _HTML_HEADERS.copy()
    if referer:
        headers["Referer"] = referer
    
    try:
        # stream=True позволяет прочитать заголовки до загрузки всего тела
        response = session.get(resolved, headers=headers, timeout=_TIMEOUT, stream=True)
        response.raise_for_status()
        
        # Пытаемся достать имя файла из Content-Disposition
        filename = None
        cd = response.headers.get("Content-Disposition")
        if cd:
            # Try RFC 5987 filename*=UTF-8''...
            m_utf8 = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
            if m_utf8:
                filename = unquote(m_utf8.group(1))
            else:
                # Try double quoted filename="..."
                m_quoted = re.search(r'filename="([^"]+)"', cd, re.IGNORECASE)
                if m_quoted:
                    filename = m_quoted.group(1)
                else:
                    # Try unquoted filename=...
                    m_unquoted = re.search(r'filename=([^;]+)', cd, re.IGNORECASE)
                    if m_unquoted:
                        filename = m_unquoted.group(1).strip(" \"'")
        
        return response.content, filename
    except requests.RequestException as e:
        print(f"  [E-DISCLOSURE FILE] Ошибка загрузки: {e}", flush=True)
        return None, None


def sanitize_filename(filename: str, max_length: int = 50) -> str:
    """Очищает имя файла от запрещенных символов и ограничивает его длину."""
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe_name = re.sub(r'[\x00-\x1f\x7f]', '', safe_name)
    
    if len(safe_name) <= max_length:
        return safe_name
        
    path = Path(safe_name)
    ext = path.suffix
    stem = path.stem
    
    hash_str = hashlib.md5(filename.encode('utf-8', errors='ignore')).hexdigest()[:6]
    
    allowed_stem_len = max_length - len(hash_str) - 1 - len(ext)
    
    if allowed_stem_len > 0:
        return f"{stem[:allowed_stem_len]}_{hash_str}{ext}"
    else:
        return f"{hash_str}{ext}"[:max_length]


def extract_zip_to_dir(content: bytes, extract_dir: Path) -> Dict[str, str]:
    """Извлекает содержимое ZIP-архива в директорию. Возвращает маппинг {safe_name: original_name}."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r", metadata_encoding="cp866") as zf:
            for name in zf.namelist():
                if name.endswith("/") or ".." in name:
                    continue
                base_name = Path(name).name
                if not base_name:
                    continue
                safe_name = sanitize_filename(base_name)
                target_path = extract_dir / safe_name
                try:
                    with zf.open(name, "r") as src:
                        target_path.write_bytes(src.read())
                except (zipfile.BadZipFile, OSError) as e:
                    print(f"  [ZIP] Ошибка извлечения {name}: {e}", flush=True)
                    continue
                result[safe_name] = base_name
    except zipfile.BadZipFile as e:
        print(f"  [ZIP] Невалидный архив: {e}", flush=True)
    return result


def extract_rar_to_dir(file_path: Path, extract_dir: Path) -> Dict[str, str]:
    """Извлекает содержимое RAR-архива в директорию.
    
    Поддерживает многотомные архивы, если передан путь к первому тому.
    Для работы требуется установленная утилита unrar.
    Возвращает маппинг {safe_name: original_name}.
    """
    extract_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    try:
        with rarfile.RarFile(file_path) as rf:
            for info in rf.infolist():
                if info.isdir() or ".." in info.filename:
                    continue
                base_name = Path(info.filename).name
                if not base_name:
                    continue
                safe_name = sanitize_filename(base_name)
                target_path = extract_dir / safe_name
                try:
                    with rf.open(info.filename, "r") as src:
                        target_path.write_bytes(src.read())
                except (rarfile.Error, OSError, EOFError) as e:
                    print(f"  [RAR] Ошибка извлечения {info.filename}: {e}", flush=True)
                    # Если данных не хватает, возможно файл поврежден или не все тома доступны
                    if "read enough data" in str(e).lower():
                        print(f"  [RAR] Критическая ошибка: данные неполные. Возможно, отсутствуют тома.", flush=True)
                    continue
                result[safe_name] = base_name
    except rarfile.Error as e:
        print(f"  [RAR] Невалидный архив или отсутствует unrar: {e}", flush=True)
    return result


def extract_archive_to_dir(file_path: Path, extract_dir: Path) -> Dict[str, str]:
    """Определяет тип архива по расширению и извлекает его."""
    ext = file_path.suffix.lower()
    if ext == ".zip":
        return extract_zip_to_dir(file_path.read_bytes(), extract_dir)
    if ext == ".rar":
        return extract_rar_to_dir(file_path, extract_dir)
    return {}


def clean_markdown_after_pdf2md(content: str) -> str:
    """Очищает сырой markdown от pdf2md перед сохранением."""
    content = content.replace("\u00a0", " ")
    content = re.sub(r"(\d+(?:\.\d+)*)\\.", r"\1.", content)
    content = content.replace("\\-", "-").replace("\\\n", "\n").replace("\\\r", "\r")
    content = re.sub(r"^\s*<!-- -->\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^\s*#+\s*$", "", content, flags=re.MULTILINE)
    is_amendments_doc = bool(_AMENDMENTS_PHRASE_PATTERN.search(content))
    header_match = None if is_amendments_doc else re.search(_BOND_DECISION_PHRASE, content, re.IGNORECASE)
    if header_match:
        content = content[header_match.start():]
        content = re.sub(r"Утверждено\s+решением.*?(?=Вид,\s*категория\s*\([^)]*\),?\s*ценных\s*бумаг)", "", content, flags=re.DOTALL | re.IGNORECASE)
    return content
