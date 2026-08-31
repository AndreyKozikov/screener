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

# Базовые заголовки сессии
_BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Заголовки для API запросов
_API_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.e-disclosure.ru",
    "Referer": "https://www.e-disclosure.ru/poisk-po-kompaniyam",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# Заголовки для HTML страниц
_HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
}

_URL = "https://www.e-disclosure.ru/api/search/companies"
_EVENTS_URL = "https://www.e-disclosure.ru/api/events/page"
_EVENT_PAGE_URL = "https://www.e-disclosure.ru/portal/event.aspx"
_SEARCH_PAGE_URL = "https://www.e-disclosure.ru/poisk-po-kompaniyam"
_MAIN_PAGE_URL = "https://www.e-disclosure.ru"
_TIMEOUT = 30  # Увеличен таймаут для медленных соединений

# Параллельная загрузка HTML текстов событий только внутри одного года
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
_CHAR_MAP: Dict[str, str] = {
    "А": "A", "В": "B", "С": "C", "Е": "E", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X",
    "а": "a", "с": "c", "е": "e", "к": "k",
    "м": "m", "о": "o", "р": "p", "х": "x",
}





def _extract_event_text(pseudo_guid: str, session: requests.Session) -> Optional[str]:
    """Извлекает текст события из HTML страницы по pseudoGUID."""
    page_url = f"{_EVENT_PAGE_URL}?EventId={pseudo_guid}"
    html_headers = {k: v for k, v in _HTML_HEADERS.items()}
    html_headers.pop("X-Requested-With", None)
    page_response = session.get(page_url, headers=html_headers, timeout=_TIMEOUT)
    page_response.raise_for_status()
    page_html = page_response.text

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

    div_pattern = (
        r'<div\s+style="[^"]*word-break:\s*break-word[^"]*"[^>]*>'
    )
    div_matches = list(re.finditer(div_pattern, cont_wrap_content, re.IGNORECASE))
    if not div_matches:
        return None
    target_match = div_matches[1] if len(div_matches) > 1 else div_matches[0]

    content_start = target_match.end()
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
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = html.unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()

    return text


def clean_event_text(text: str) -> str:
    """Удаляет из текста события лишние блоки и маркеры для упрощения анализа LLM."""
    text = re.sub(
        r"1\. Общие сведения.*?2\. Содержание сообщения",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"3\. Подпись.*", "", text, flags=re.DOTALL)
    text = re.sub(r"^\d+\.\d+\.\s*", "", text, flags=re.MULTILINE)
    text = text.replace("2. Содержание сообщения", "")
    return text.strip()


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
    reg_num_lat: str,
) -> bool:
    """Проверяет, содержит ли текст события полный регистрационный номер.

    Нормализует текст события (заменяет кириллицу на латиницу для визуально схожих символов)
    и ищет в нём латинскую версию регистрационного номера.

    Args:
        text: Текст события.
        reg_num_lat: Регистрационный номер в латинской нормализации.

    Returns:
        ``True``, если в тексте найден номер; иначе ``False``.
    """
    if not text or not reg_num_lat:
        return False

    # Нормализуем текст события: переводим в нижний регистр и заменяем кириллицу на латиницу
    text_norm = text.lower()
    for ru_char, lat_char in _CHAR_MAP.items():
        text_norm = text_norm.replace(ru_char.lower(), lat_char.lower())

    return reg_num_lat.lower() in text_norm


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


def _find_all_events_sorted_by_date(
    events: List[Dict[str, Any]],
    date_obj: date,
) -> List[Dict[str, Any]]:
    """Возвращает все события строго раньше ``date_obj``, отсортированные от новых к старым."""
    filtered: List[Tuple[date, Dict[str, Any]]] = []
    for event in events:
        event_name = (event.get("eventName") or "").strip()
        if event_name == _EXCLUDED_EVENT_TITLE:
            continue
        event_date_str = event.get("eventDate")
        if not event_date_str:
            continue
        try:
            # Надежный парсинг даты (учитываем возможные форматы и наличие времени)
            date_part = str(event_date_str)[:10]
            if "-" in date_part:
                event_date = datetime.strptime(date_part, "%Y-%m-%d").date()
            elif "." in date_part:
                event_date = datetime.strptime(date_part, "%d.%m.%Y").date()

            else:
                event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
            
        # Ограничение по конкретной дате снято: возвращаем все события года
        filtered.append((event_date, event))


    filtered.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in filtered]


def find_events_by_reg_number(
    date: str,
    company_id: int,
    reg_number: str,
) -> List[Dict[str, Optional[str]]]:
    """Загружает все события компании за год и возвращает те, что содержат регистрационный номер."""
    if not reg_number.strip():
        return []

    session, _ = _get_session()

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    year = date_obj.year

    params = {"companyId": company_id, "year": year}
    print(f"  [API] GET {_EVENTS_URL}?companyId={company_id}&year={year}", flush=True)
    response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    events = response.json()

    sorted_events = _find_all_events_sorted_by_date(events, date_obj)

    # Нормализация номера
    _, reg_num_lat = normalize_reg_number(reg_number)

    result: List[Dict[str, Optional[str]]] = []
    for event in sorted_events:
        pseudo_guid = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        text = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        if event_text_matches_reg_number(text, reg_num_lat):
            result.append({
                "event_name": event.get("eventName") or "",
                "event_date": _format_event_date(event.get("eventDate")),
                "pseudo_guid": pseudo_guid,
                "full_text": text,
                "text": clean_event_text(text),
            })

    return result


def get_events_with_full_text_for_year(
    company_id: int,
    year: int,
) -> List[Dict[str, Any]]:
    """Загружает все события компании за конкретный календарный год с полным текстом."""
    far_future: date = date(9999, 12, 31)

    session, _ = _get_session()
    params: Dict[str, Any] = {"companyId": company_id, "year": year}
    print(f"  [API] GET {_EVENTS_URL}?companyId={company_id}&year={year}", flush=True)
    response: requests.Response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    if response.status_code == 403:
        _clear_session_cache()
        session, _ = _get_session()
        response = session.get(_EVENTS_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    events: Any = response.json()

    sorted_events: List[Dict[str, Any]] = _find_all_events_sorted_by_date(events, far_future)

    result: List[Dict[str, Any]] = []
    for event in sorted_events:
        pseudo_guid: Optional[str] = event.get("pseudoGUID")
        if not pseudo_guid:
            continue
        text: Optional[str] = _extract_event_text(pseudo_guid, session)
        if not text:
            continue
        result.append({
            "event_name": event.get("eventName") or "",
            "event_date": _format_event_date(event.get("eventDate")),
            "pseudo_guid": pseudo_guid,
            "full_text": text,
            "text": clean_event_text(text),
        })

    return result


def fetch_emission_documents_page(edisclosure_id: int) -> str:
    """Загружает HTML-страницу эмиссионных документов эмитента с e-disclosure.ru."""
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
    if u.startswith(("http://", "https://")):
        return u
    return urljoin(_MAIN_PAGE_URL + "/", u.lstrip("/"))


def download_emission_file(file_url: str) -> Optional[bytes]:
    """Скачивает файл по ссылке с e-disclosure.ru."""
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
    """Извлекает содержимое ZIP-архива в директорию."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    result: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r", metadata_encoding="cp866") as zf:
            for name in zf.namelist():
                if name.endswith("/") or not _is_safe_archive_member(name):
                    print(
                        f"  [ZIP] Пропуск подозрительного пути в архиве: {ascii(name)}",
                        flush=True,
                    )
                    continue
                base_name: str = Path(name).name
                if not base_name:
                    continue
                target_path: Path = extract_dir / base_name
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


def _is_safe_archive_member(name: str) -> bool:
    """Проверяет, что имя файла внутри архива не ведет к path traversal."""
    normalized = (name or "").replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:/", normalized):
        return False

    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    return all(part != ".." for part in parts)


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
