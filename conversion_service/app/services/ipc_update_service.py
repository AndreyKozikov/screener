"""Сервис автоматического обновления месячных индексов потребительских цен Росстата.

Задача запускается планировщиком 20–30 числа каждого месяца в 19:00 МСК.
После успешной загрузки и записи в БД фиксирует месяц в state-файле, чтобы
не повторять обновление в том же календарном месяце.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from conversion_service.app.repository.db.client import get_db_repository_client
from conversion_service.app.services.ipc_service import get_ipc_service
from conversion_service.app.utils.rosstat_ipc_monthly_links_parser import (
    RosstatIpcMonthlyFileLink,
    resolve_latest_ipc_monthly_link,
)
from conversion_service.config.settings import settings

logger = logging.getLogger(__name__)

_SERVICE_DIR: Path = Path(__file__).resolve().parent.parent.parent
_STATE_FILE_NAME = "ipc.last_success"
_MONTH_KEY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")

LinkResolver = Callable[[str, int], Optional[RosstatIpcMonthlyFileLink]]
MonthKey = Tuple[int, int]


def _resolve_link(page_url: str, timeout: int) -> Optional[RosstatIpcMonthlyFileLink]:
    """Резолвер ссылки с настройками Росстата."""
    return resolve_latest_ipc_monthly_link(
        page_url,
        verify_ssl=settings.IPC_VERIFY_SSL,
        timeout=timeout,
    )


class IpcUpdateService:
    """Обновляет месячные ИПЦ по самой свежей ссылке со страницы Росстата."""

    def __init__(
        self,
        ipc_service: Any | None = None,
        db_client: Any | None = None,
        link_resolver: LinkResolver | None = None,
        state_path: Path | None = None,
    ) -> None:
        self._ipc_service = ipc_service or get_ipc_service()
        self._db_client = db_client or get_db_repository_client()
        self._link_resolver = link_resolver or _resolve_link
        self._state_path = state_path or (
            _SERVICE_DIR / "scheduled_updates" / "state" / _STATE_FILE_NAME
        )

    async def run(self, today: date | None = None) -> Dict[str, Any]:
        """Выполняет одну попытку обновления.

        Returns:
            Словарь со статусом ``completed`` или ``not_completed``.
        """
        current = today or date.today()
        checked_at = current.isoformat()

        if self._read_completed_month() == (current.year, current.month):
            logger.info(
                "[IPC UPDATE] Обновление уже выполнено в %s",
                self._format_month(current.year, current.month),
            )
            return {
                "status": "completed",
                "action": "skipped",
                "month": self._format_month(current.year, current.month),
                "checked_at": checked_at,
            }

        page_url = settings.IPC_PAGE_URL
        timeout = settings.IPC_HTTP_TIMEOUT_SECONDS
        link = await asyncio.to_thread(self._link_resolver, page_url, timeout)

        if link is None:
            logger.warning(
                "[IPC UPDATE] На странице не найдена ссылка на месячный файл ИПЦ"
            )
            return {
                "status": "not_completed",
                "reason": "link_not_found",
                "checked_at": checked_at,
            }

        db_month = await self._get_last_db_month()
        if db_month is not None and link.month_key <= db_month:
            logger.info(
                "[IPC UPDATE] Нового месяца нет: в БД %s, на странице %s",
                self._format_month(*db_month),
                self._format_month(*link.month_key),
            )
            return {
                "status": "not_completed",
                "reason": "no_new_month",
                "db_month": self._format_month(*db_month),
                "link_month": self._format_month(*link.month_key),
                "checked_at": checked_at,
            }

        logger.info(
            "[IPC UPDATE] Загрузка файла за %s: %s",
            self._format_month(*link.month_key),
            link.url,
        )
        await self._ipc_service.download_parse_and_save(url=link.url)

        verified_month = await self._get_last_db_month()
        if verified_month is None or verified_month < link.month_key:
            raise RuntimeError(
                "После обновления последний месяц ИПЦ в БД не соответствует файлу: "
                f"link={self._format_month(*link.month_key)}, "
                f"db={self._format_month(*verified_month) if verified_month else 'нет данных'}"
            )

        # Файл ИПЦ публикуется за предыдущий месяц и содержит всю историю,
        # поэтому после успешной записи фиксируем текущий календарный месяц.
        self._write_completed_month(current)

        logger.info(
            "[IPC UPDATE] Обновление завершено за %s",
            self._format_month(*link.month_key),
        )
        return {
            "status": "completed",
            "action": "updated",
            "url": link.url,
            "month": self._format_month(*link.month_key),
            "checked_at": checked_at,
        }

    async def _get_last_db_month(self) -> Optional[MonthKey]:
        """Возвращает последний месяц ИПЦ из БД."""
        response = await asyncio.to_thread(
            self._db_client.post,
            "/api/ipc_monthly_get",
            json={},
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None

        last = rows[-1]
        value = (
            last.get("record_data")
            if isinstance(last, dict)
            else getattr(last, "record_data", None)
        )
        if value is None:
            return None

        parsed = date.fromisoformat(str(value)[:10])
        return parsed.year, parsed.month

    def _read_completed_month(self) -> Optional[MonthKey]:
        """Читает месяц последнего успешного обновления из state-файла."""
        try:
            text = self._state_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.warning(
                "[IPC UPDATE] Не удалось прочитать state-файл %s: %s",
                self._state_path,
                exc,
            )
            return None

        match = _MONTH_KEY_PATTERN.fullmatch(text)
        if match is None:
            return None
        month = int(match.group(2))
        if not 1 <= month <= 12:
            return None
        return int(match.group(1)), month

    def _write_completed_month(self, current: date) -> None:
        """Атомарно записывает месяц успешного обновления в state-файл."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._state_path.with_name(self._state_path.name + ".tmp")
        temp_path.write_text(
            f"{current.year:04d}-{current.month:02d}\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self._state_path)

    @staticmethod
    def _format_month(year: int, month: int) -> str:
        return f"{year:04d}-{month:02d}"


_ipc_update_service: Optional[IpcUpdateService] = None


def get_ipc_update_service() -> IpcUpdateService:
    """Возвращает синглтон-экземпляр сервиса обновления ИПЦ."""
    global _ipc_update_service
    if _ipc_update_service is None:
        _ipc_update_service = IpcUpdateService()
    return _ipc_update_service
