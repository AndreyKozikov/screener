"""Gunicorn-воркер для backend с частым heartbeat для uvicorn.

Gunicorn считает воркер живым по файлу heartbeat. Базовый ``UvicornWorker``
сообщает heartbeat раз в ``gunicorn_timeout`` секунд, поэтому длинный запрос
обновления (до 6 часов) мог быть принят арбитром за зависший. Уменьшаем
интервал уведомлений, не меняя общий gunicorn timeout.
"""

from __future__ import annotations

from typing import Any

from uvicorn.workers import UvicornWorker


class BondsScreenerUvicornWorker(UvicornWorker):
    """UvicornWorker с heartbeat раз в 30 секунд."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.config.timeout_notify = 30
