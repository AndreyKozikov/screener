"""Конфигурация проекта BondsScreener.

Пакет содержит настройки приложения (settings) и пути к данным/БД/API (paths).
Импорт: from config import settings; from config.paths import DATA_DIR, DB_PATH, ...
"""

from config.settings import settings

__all__ = ["settings"]
