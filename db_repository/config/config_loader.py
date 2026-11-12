"""Загрузка несекретной конфигурации db_repository из config.toml.

Секреты (API-ключ) остаются в .env и читаются pydantic-settings.
TOML-значения применяются как значения по умолчанию: если одноимённая
переменная окружения задана явно, она имеет приоритет.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

SERVICE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = SERVICE_DIR / "config" / "config.toml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Прочитать config.toml; отсутствующий файл означает пустой словарь."""
    config_path = Path(path) if path is not None else CONFIG_PATH
    if not config_path.is_file():
        return {}
    with config_path.open("rb") as file:
        return tomllib.load(file)


def resolve_path(value: str | Path | None, default: Path) -> Path:
    """Разрешить путь относительно каталога сервиса, а не текущего cwd."""
    candidate = Path(value) if value not in (None, "") else Path(default)
    if not candidate.is_absolute():
        candidate = SERVICE_DIR / candidate
    return candidate.resolve()


def env_is_set(field_name: str, prefix: str = "DB_REPOSITORY_") -> bool:
    """Проверить, задана ли переменная окружения для поля настроек."""
    return f"{prefix}{field_name.upper()}" in os.environ
