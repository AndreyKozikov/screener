"""Settings for the database service boundary.

Секреты читаются из db_repository/.env (префикс DB_REPOSITORY_).
Несекретные настройки читаются из db_repository/config/config.toml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from db_repository.config.config_loader import env_is_set, load_config

_SERVICE_DIR = Path(__file__).resolve().parent.parent
_env_file = _SERVICE_DIR / ".env"
_env_file_path = str(_env_file) if _env_file.is_file() else None


class DatabaseServiceSettings(BaseSettings):
    api_key: SecretStr = SecretStr("")

    host: str = "0.0.0.0"
    port: int = 8964
    workers: int = 1
    reload: bool = False
    log_level: str = "info"
    run_migrations_on_startup: bool = True
    require_api_key: bool = True

    db_dir: str = "./data/db"
    data_dir: str = "./data"
    log_dir: str = "./logs"
    db_filename: str = "bonds.db"
    blog_db_filename: str = "blog.db"
    history_db_filename: str = "history_db.db"
    portfolio_db_filename: str = "portfolios.db"

    sqlite_busy_timeout_ms: int = 30000

    model_config = SettingsConfigDict(
        env_prefix="DB_REPOSITORY_",
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: Any) -> None:
        config = load_config()
        server = config.get("server", {})
        security = config.get("security", {})
        paths = config.get("paths", {})
        database = config.get("database", {})

        defaults = {
            "host": server.get("host"),
            "port": server.get("port"),
            "workers": server.get("workers"),
            "reload": server.get("reload"),
            "log_level": server.get("log_level"),
            "run_migrations_on_startup": server.get("run_migrations_on_startup"),
            "require_api_key": security.get("require_api_key"),
            "db_dir": paths.get("db_dir"),
            "data_dir": paths.get("data_dir"),
            "log_dir": paths.get("log_dir"),
            "db_filename": paths.get("db_filename"),
            "blog_db_filename": paths.get("blog_db_filename"),
            "history_db_filename": paths.get("history_db_filename"),
            "portfolio_db_filename": paths.get("portfolio_db_filename"),
            "sqlite_busy_timeout_ms": database.get("sqlite_busy_timeout_ms"),
        }
        for field_name, value in defaults.items():
            if value is not None and not env_is_set(field_name):
                setattr(self, field_name, value)


settings = DatabaseServiceSettings()
