# -*- coding: utf-8 -*-
"""Парсер ссылки на месячный Excel-файл ИПЦ Росстата.

Страница: https://rosstat.gov.ru/statistics/price
Подраздел: «Индексы потребительских цен».
Целевой пункт: «Индексы потребительских цен на товары и услуги по Российской
Федерации, федеральным округам и субъектам Российской Федерации (с 2022 г.)».
Ссылка на файл: /storage/mediabank/ipc_RF_fo_sub_MM-YYYY.xlsx
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)

ROSSTAT_BASE_URL = "https://rosstat.gov.ru"
DEFAULT_PAGE_URL = "https://rosstat.gov.ru/statistics/price"
DEFAULT_TIMEOUT_SECONDS = 30

TARGET_TITLE = (
    "Индексы потребительских цен на товары и услуги по Российской Федерации, "
    "федеральным округам и субъектам Российской Федерации (с 2022 г.)"
)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Ссылка на накопительный месячный файл ИПЦ: ipc_RF_fo_sub_MM-YYYY.xlsx.
_MONTHLY_FILE_HREF_PATTERN = re.compile(
    r'href="([^"]*ipc_RF_fo_sub_(\d{2})-(\d{4})\.xlsx)"',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RosstatIpcMonthlyFileLink:
    """Ссылка на накопительный Excel-файл ИПЦ за конкретный месяц."""

    url: str
    year: int
    month: int

    @property
    def month_key(self) -> tuple[int, int]:
        return self.year, self.month


def _absolute_url(href: str) -> str:
    """Преобразует href в абсолютный URL Росстата."""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("/"):
        return f"{ROSSTAT_BASE_URL}{href}"
    return f"{ROSSTAT_BASE_URL}/{href}"


def extract_ipc_monthly_links(html: str) -> List[RosstatIpcMonthlyFileLink]:
    """Извлекает все ссылки на накопительный месячный файл ИПЦ из HTML."""
    links: dict[str, RosstatIpcMonthlyFileLink] = {}

    for match in _MONTHLY_FILE_HREF_PATTERN.finditer(html):
        href, month_text, year_text = match.groups()
        month = int(month_text)
        if not 1 <= month <= 12:
            continue

        url = _absolute_url(href)
        links.setdefault(
            url,
            RosstatIpcMonthlyFileLink(
                url=url,
                year=int(year_text),
                month=month,
            ),
        )

    return list(links.values())


def _fetch_html(page_url: str, *, verify_ssl: bool, timeout: int) -> str:
    """Загружает HTML страницы Росстата."""
    with warnings.catch_warnings():
        if not verify_ssl:
            warnings.simplefilter("ignore")

        response = requests.get(
            page_url,
            headers=_DEFAULT_HEADERS,
            verify=verify_ssl,
            timeout=timeout,
        )

    response.raise_for_status()
    return response.text


def fetch_ipc_monthly_links(
    page_url: str = DEFAULT_PAGE_URL,
    *,
    verify_ssl: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> List[RosstatIpcMonthlyFileLink]:
    """Загружает страницу Росстата и возвращает ссылки на месячные файлы ИПЦ."""
    logger.info("[ROSSTAT IPC MONTHLY PARSER] Загрузка страницы: %s", page_url)
    html = _fetch_html(page_url, verify_ssl=verify_ssl, timeout=timeout)

    if TARGET_TITLE not in html:
        logger.warning(
            "[ROSSTAT IPC MONTHLY PARSER] Целевой пункт не найден в HTML: %s",
            TARGET_TITLE,
        )

    links = extract_ipc_monthly_links(html)
    logger.info("[ROSSTAT IPC MONTHLY PARSER] Найдено ссылок: %d", len(links))
    return links


def select_latest_link(
    links: Iterable[RosstatIpcMonthlyFileLink],
) -> Optional[RosstatIpcMonthlyFileLink]:
    """Возвращает ссылку с максимальным месяцем или None."""
    latest: Optional[RosstatIpcMonthlyFileLink] = None
    for link in links:
        if latest is None or link.month_key > latest.month_key:
            latest = link
    return latest


def resolve_latest_ipc_monthly_link(
    page_url: str = DEFAULT_PAGE_URL,
    *,
    verify_ssl: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[RosstatIpcMonthlyFileLink]:
    """Загружает страницу и возвращает ссылку на самый свежий месячный файл ИПЦ."""
    return select_latest_link(
        fetch_ipc_monthly_links(page_url, verify_ssl=verify_ssl, timeout=timeout)
    )
