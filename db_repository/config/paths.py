"""Пути db_repository, построенные от собственного каталога сервиса.

Ни один путь не выводится из каталога backend: сервис полностью автономен.
Источник значений — config/config.toml (см. config.settings).
"""

from pathlib import Path
import os

from db_repository.config.config_loader import resolve_path
from db_repository.config.settings import settings

SERVICE_DIR: Path = Path(__file__).resolve().parent.parent

DB_DIR: Path = resolve_path(settings.db_dir, SERVICE_DIR / "data" / "db")
DATA_DIR: Path = resolve_path(settings.data_dir, SERVICE_DIR / "data")
LOG_DIR: Path = resolve_path(settings.log_dir, SERVICE_DIR / "logs")

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = DATA_DIR / "events"

# Файлы баз данных SQLite
DB_PATH: Path = DB_DIR / settings.db_filename
BLOG_DB_PATH: Path = DB_DIR / settings.blog_db_filename
HISTORY_DB_PATH: Path = DB_DIR / settings.history_db_filename

_portfolio_override = os.getenv("PORTFOLIO_DB_PATH")
PORTFOLIO_DB_PATH: Path = resolve_path(
    _portfolio_override,
    DB_DIR / settings.portfolio_db_filename,
)
