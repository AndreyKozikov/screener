"""Резолвер ссылок на Excel-файлы инфляционных ожиданий Банка России.

Страница: https://cbr.ru/statistics/ddkp/inflationary_expectations/
Раздел: «Статистические данные».
Ссылки имеют вид /Collection/Collection/File/<id>/Infl_exp_YY-MM.xlsx.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)

CBR_BASE_URL = "https://cbr.ru"
DEFAULT_PAGE_URL = "https://cbr.ru/statistics/ddkp/inflationary_expectations/"
DEFAULT_TIMEOUT_SECONDS = 30

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Блок ссылки версии файла на странице ЦБ.
_ANCHOR_PATTERN = re.compile(
    r'<a\b[^>]*\bclass="versions_item"[^>]*>.*?</a>',
    re.DOTALL,
)
# Прямая ссылка на xlsx-файл инфляционных ожиданий.
_FILE_HREF_PATTERN = re.compile(
    r'href="(/Collection/Collection/File/\d+/(?:stat_)?Infl_exp_(\d{2})-(\d{2})\.xlsx)"',
    re.IGNORECASE,
)
# Дата публикации из подсказки ссылки.
_PUBLISHED_PATTERN = re.compile(r'data-tooltip-content="Опубликовано ([^"]+)"')
# Видимый текст ссылки, например «Ноябрь 2026 года».
_LABEL_PATTERN = re.compile(r'>([^<]*)</a>')


@dataclass(frozen=True)
class InflationExpectationsFileLink:
    """Ссылка на файл инфляционных ожиданий за конкретный месяц."""

    url: str
    label: str
    year: int
    month: int
    published: str

    @property
    def month_key(self) -> tuple[int, int]:
        return self.year, self.month


def _clean_text(value: str) -> str:
    """Убирает HTML-сущности и лишние пробелы в тексте ссылки."""
    return re.sub(r"\s+", " ", html_lib.unescape(value or "")).strip()


def extract_inflation_expectations_links(
    html: str,
) -> List[InflationExpectationsFileLink]:
    """Извлекает все xlsx-ссылки инфляционных ожиданий из HTML страницы.

    Возвращает ссылки без дублей в порядке появления на странице.
    """
    links: dict[str, InflationExpectationsFileLink] = {}

    for anchor in _ANCHOR_PATTERN.findall(html):
        href_match = _FILE_HREF_PATTERN.search(anchor)
        if href_match is None:
            continue

        href, year_suffix, month_text = href_match.groups()
        year = 2000 + int(year_suffix)
        month = int(month_text)
        if not 1 <= month <= 12:
            continue

        published_match = _PUBLISHED_PATTERN.search(anchor)
        label_match = _LABEL_PATTERN.search(anchor)
        link = InflationExpectationsFileLink(
            url=f"{CBR_BASE_URL}{href}",
            label=_clean_text(label_match.group(1)) if label_match else "",
            year=year,
            month=month,
            published=_clean_text(published_match.group(1)) if published_match else "",
        )
        links.setdefault(link.url, link)

    return list(links.values())


def fetch_inflation_expectations_links(
    page_url: str = DEFAULT_PAGE_URL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> List[InflationExpectationsFileLink]:
    """Загружает страницу ЦБ и возвращает список xlsx-ссылок."""
    logger.info("[CBR INFLATION EXPECTATIONS] Загрузка страницы: %s", page_url)
    response = requests.get(page_url, headers=_DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    links = extract_inflation_expectations_links(response.text)
    logger.info("[CBR INFLATION EXPECTATIONS] Найдено ссылок: %d", len(links))
    return links


def select_latest_link(
    links: Iterable[InflationExpectationsFileLink],
) -> Optional[InflationExpectationsFileLink]:
    """Возвращает ссылку с максимальным месяцем или None."""
    latest: Optional[InflationExpectationsFileLink] = None
    for link in links:
        if latest is None or link.month_key > latest.month_key:
            latest = link
    return latest


def resolve_latest_inflation_expectations_link(
    page_url: str = DEFAULT_PAGE_URL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[InflationExpectationsFileLink]:
    """Загружает страницу и возвращает ссылку на самый свежий файл."""
    return select_latest_link(fetch_inflation_expectations_links(page_url, timeout))
