# -*- coding: utf-8 -*-
"""Parser for weekly CPI report links from the Rosstat compendium page.

Fetches https://rosstat.gov.ru/compendium/document/50798, finds the section
'Срочная информация (по темам)' -> 'Об оценке индекса потребительских цен
(еженедельная)' and extracts all HTML report links of the form:
    https://rosstat.gov.ru/storage/mediabank/<id>_<dd-mm-yyyy>.html
"""

import logging
import re
import warnings
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rosstat uses a self-signed / non-standard CA certificate, so we suppress
# the InsecureRequestWarning when verify=False is used.
_REQUEST_TIMEOUT_SEC: int = 30
_DEFAULT_HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Regex patterns
_TOGGLE_TITLE_PATTERN: re.Pattern = re.compile(
    r'<div class="toggle-card__title">(.*?)</div>',
    re.DOTALL,
)
_MEDIABANK_LINK_PATTERN: re.Pattern = re.compile(
    r'href="(/storage/mediabank/\d+_\d{2}-\d{2}-\d{4}\.html)"'
)

# Keyword to locate the correct subsection.
# Exact target title: "Об оценке индекса потребительских цен (еженедельная)"
# The unique substring "оценке индекса" (lowercase middle part) is used so the
# search is case-insensitive to the leading capital letter and avoids matching
# "О потребительских ценах на нефтепродукты (еженедельная)".
# Defined via bytes.fromhex() — pure ASCII, no encoding issues regardless of
# how the source file is saved.
# "оценке индекса" UTF-8: d0be d186 d0b5 d0bd d0ba d0b5 20 d0b8 d0bd d0b4 d0b5 d0ba d181 d0b0
_SECTION_KEYWORD: str = bytes.fromhex(
    "d0bed186d0b5d0bdd0bad0b5"  # оценке
    "20"                         # space
    "d0b8d0bdd0b4d0b5d0bad181d0b0"  # индекса
).decode("utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_weekly_ipc_links(
    url: str,
    *,
    verify_ssl: bool = False,
    timeout: int = _REQUEST_TIMEOUT_SEC,
) -> List[str]:
    """Fetch the Rosstat compendium page and return all weekly CPI report URLs.

    The function is intentionally synchronous so it can be called both from
    scripts and from FastAPI endpoints via ``asyncio.to_thread``.

    Args:
        url: Compendium page URL. Defaults to ``COMPENDIUM_URL``.
        verify_ssl: Whether to verify the SSL certificate. Rosstat uses a
            certificate signed by a non-standard CA, so ``False`` is the
            safe default for on-premises usage.
        timeout: Request timeout in seconds.

    Returns:
        List of absolute URLs in page order (newest report first).

    Raises:
        requests.HTTPError: If the server returns a non-2xx response.
        ValueError: If the weekly CPI subsection cannot be located on the page.
    """

    html = _fetch_html(url, verify_ssl=verify_ssl, timeout=timeout)
    links = _extract_weekly_ipc_links(html)

    logger.info("[ROSSTAT PARSER] Extracted %d weekly IPC report links", len(links))
    return links


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fetch_html(url: str, *, verify_ssl: bool, timeout: int) -> str:
    """Download the page and return decoded HTML text.

    The page is served as UTF-8 (Content-Type charset=UTF-8). ``requests``
    auto-detects this correctly, so we rely on the detected encoding.
    """
    with warnings.catch_warnings():
        if not verify_ssl:
            warnings.simplefilter("ignore")  # suppress InsecureRequestWarning

        response = requests.get(
            url,
            headers=_DEFAULT_HEADERS,
            verify=verify_ssl,
            timeout=timeout,
        )

    response.raise_for_status()
    return response.text


def _extract_weekly_ipc_links(html: str) -> List[str]:
    """Parse HTML and return absolute links from the weekly IPC subsection.

    Strategy (no external HTML parser required):
      1. Collect positions of all ``toggle-card__title`` div start tags.
      2. Find the title whose text contains *\u0435\u0436\u0435\u043d\u0435\u0434\u0435\u043b\u044c\u043d\u0430\u044f* (weekly).
      3. Slice the HTML from that title to the *next* title at the same level.
      4. Extract all ``/storage/mediabank/*.html`` hrefs from that block.
      5. Prepend the Rosstat base URL to make links absolute.

    Raises:
        ValueError: If the weekly subsection title is not found.
    """
    # Collect (char_position, inner_text) for every toggle-card__title
    title_spans: List[tuple] = [
        (m.start(), m.group(1).strip())
        for m in _TOGGLE_TITLE_PATTERN.finditer(html)
    ]

    if not title_spans:
        raise ValueError(
            "No toggle-card__title elements found on the page "
            "— page structure may have changed."
        )

    # Find the weekly-CPI title
    weekly_index: Optional[int] = None
    for idx, (_, title_text) in enumerate(title_spans):
        if _SECTION_KEYWORD in title_text:
            weekly_index = idx
            logger.debug(
                "[ROSSTAT PARSER] Found weekly IPC title at index %d: %r",
                idx,
                title_text,
            )
            break

    if weekly_index is None:
        raise ValueError(
            f"Weekly IPC subsection (keyword: '{_SECTION_KEYWORD}') not found "
            "on the page. The Rosstat page structure may have changed."
        )

    # Determine slice boundaries
    section_start: int = title_spans[weekly_index][0]
    section_end: int = (
        title_spans[weekly_index + 1][0]
        if weekly_index + 1 < len(title_spans)
        else len(html)
    )

    block = html[section_start:section_end]
    logger.debug(
        "[ROSSTAT PARSER] Weekly IPC block: chars %d\u2013%d (%d chars total)",
        section_start,
        section_end,
        section_end - section_start,
    )

    # Extract relative paths and convert to absolute URLs.
    # dict.fromkeys preserves insertion order while removing duplicates
    # (some documents on the page have two buttons pointing to the same URL).
    relative_paths = _MEDIABANK_LINK_PATTERN.findall(block)
    absolute_urls = list(
        dict.fromkeys(f"{ROSSTAT_BASE_URL}{path}" for path in relative_paths)
    )

    if not absolute_urls:
        logger.warning(
            "[ROSSTAT PARSER] No mediabank links found in the weekly IPC block. "
            "The page structure or content may have changed."
        )

    return absolute_urls


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    links = fetch_weekly_ipc_links()
    print(f"\nFound {len(links)} weekly IPC report links:\n")
    for link in links:
        print(link)
