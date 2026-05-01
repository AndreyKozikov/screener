import io
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

_SESSION_CACHE: Dict[str, Optional[Any]] = {
    "session": None,
    "token": None,
}

_API_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "ru,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.e-disclosure.ru",
    "Referer": "https://www.e-disclosure.ru/poisk-po-kompaniyam",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

_HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
}

_SEARCH_PAGE_URL = "https://www.e-disclosure.ru/poisk-po-kompaniyam"
_MAIN_PAGE_URL = "https://www.e-disclosure.ru"
_TIMEOUT = 30

_BOND_DECISION_PHRASE: str = "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ"
_AMENDMENTS_PHRASE_PATTERN: re.Pattern[str] = re.compile(
    r"ИЗМЕНЕНИ[ЕЯ]\s+в\s+решение\s+о\s+выпуске",
    re.IGNORECASE,
)


def _get_session_data() -> Tuple[requests.Session, str]:
    session = requests.Session()
    session.headers.update(_API_HEADERS)
    response = session.get(_SEARCH_PAGE_URL, headers=_HTML_HEADERS, timeout=_TIMEOUT)
    response.raise_for_status()
    token_match = re.search(
        r'<input[^>]*name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']',
        response.text,
        re.IGNORECASE
    )
    if not token_match:
        raise RuntimeError("Token not found")
    return session, token_match.group(1)


def _get_session() -> Tuple[requests.Session, str]:
    global _SESSION_CACHE
    if _SESSION_CACHE["session"] is not None and _SESSION_CACHE["token"] is not None:
        return _SESSION_CACHE["session"], _SESSION_CACHE["token"]
    session, token = _get_session_data()
    _SESSION_CACHE["session"] = session
    _SESSION_CACHE["token"] = token
    return session, token


def _resolve_emission_file_url(url: str) -> str:
    u: str = (url or "").strip()
    if not u:
        return u
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return urljoin(_MAIN_PAGE_URL + "/", u.lstrip("/"))


def download_emission_file(file_url: str) -> Optional[bytes]:
    resolved: str = _resolve_emission_file_url(file_url)
    if not resolved:
        return None
    session, _ = _get_session()
    try:
        response: requests.Response = session.get(
            resolved, headers=_HTML_HEADERS, timeout=_TIMEOUT
        )
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def extract_zip_to_dir(content: bytes, extract_dir: Path) -> List[str]:
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    result: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r", metadata_encoding="cp866") as zf:
            for name in zf.namelist():
                if name.endswith("/") or ".." in name:
                    continue
                base_name: str = Path(name).name
                if not base_name:
                    continue
                target_path: Path = extract_dir / base_name
                try:
                    with zf.open(name, "r") as src:
                        target_path.write_bytes(src.read())
                except (zipfile.BadZipFile, OSError):
                    continue
                result.append(base_name)
    except zipfile.BadZipFile:
        pass
    return result


def clean_markdown_after_pdf2md(content: str) -> str:
    content = content.replace("\u00a0", " ")
    content = re.sub(r"(\d+(?:\.\d+)*)\\.", r"\1.", content)
    content = content.replace("\\-", "-")
    content = content.replace("\\\n", "\n").replace("\\\r", "\r")
    content = re.sub(r"^\s*<!-- -->\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^\s*#+\s*$", "", content, flags=re.MULTILINE)

    is_amendments_doc: bool = bool(_AMENDMENTS_PHRASE_PATTERN.search(content))
    header_match: Optional[re.Match[str]] = (
        None if is_amendments_doc else re.search(_BOND_DECISION_PHRASE, content, re.IGNORECASE)
    )

    if header_match is not None:
        content = content[header_match.start():]
        content = re.sub(
            r"Утверждено\s+решением.*?(?=Вид,\s*категория\s*\([^)]*\),?\s*ценных\s*бумаг)",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    return content
