"""Загрузка несекретной конфигурации backend из config.toml.

Секреты (DB_REPOSITORY_API_KEY, AUTH_SECRET_KEY, ключи LLM) остаются в .env.
TOML-значения применяются как значения по умолчанию: переменная окружения
с тем же именем имеет приоритет.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = BACKEND_DIR / "config" / "config.toml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Прочитать config.toml; отсутствующий файл означает пустой словарь."""
    config_path = Path(path) if path is not None else CONFIG_PATH
    if not config_path.is_file():
        return {}
    with config_path.open("rb") as file:
        return tomllib.load(file)


def resolve_path(value: str | Path | None, default: Path) -> Path:
    """Разрешить путь относительно backend, а не текущего cwd."""
    candidate = Path(value) if value not in (None, "") else Path(default)
    if not candidate.is_absolute():
        candidate = BACKEND_DIR / candidate
    return candidate.resolve()


def env_is_set(field_name: str) -> bool:
    return field_name in os.environ
