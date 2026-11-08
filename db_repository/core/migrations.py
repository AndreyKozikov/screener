"""Alembic migration commands owned by the database microservice."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from db_repository.config.paths import (
    BLOG_DB_PATH,
    DB_PATH,
    HISTORY_DB_PATH,
    PORTFOLIO_DB_PATH,
)

logger = logging.getLogger(__name__)
SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SERVICE_DIR.parent


def _run_alembic(config_name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    config_path = SERVICE_DIR / config_name
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(config_path), *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _versions_dir(config_name: str) -> Path:
    return SERVICE_DIR / Path(config_name).stem / "versions"


def _upgrade(config_name: str, label: str, db_path: Path | None = None) -> None:
    config_path = SERVICE_DIR / config_name
    versions = _versions_dir(config_name)
    if not config_path.is_file() or not any(versions.glob("*.py")):
        logger.info("No %s migration scripts found; skipping", label)
        return

    arguments = []
    if db_path is not None:
        arguments.extend(["-x", f"db_path={db_path}"])
    arguments.extend(["upgrade", "head"])
    result = _run_alembic(config_name, *arguments)
    if result.returncode == 0:
        logger.info("%s database migrations applied", label)
        return

    output = f"{result.stdout or ''}{result.stderr or ''}"
    logger.error("%s database migration failed: %s", label, output)
    raise RuntimeError(f"{label} database migration failed: {output}")


def run_migrations(db_path: Path | None = None) -> None:
    """Apply the main bonds database migration chain."""
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    _upgrade("alembic.ini", "main", db_path=path)


def run_blog_migrations(db_path: Path | None = None) -> None:
    """Apply the separate blog database migration chain."""
    path = Path(db_path or BLOG_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    _upgrade("blog_alembic.ini", "blog", db_path=path)


def run_history_migrations(db_path: Path | None = None) -> None:
    """Apply the separate bond trading history database migration chain."""
    path = Path(db_path or HISTORY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    _upgrade("history_alembic.ini", "history", db_path=path)


def run_portfolio_migrations(db_path: Path | None = None) -> None:
    """Apply the separate portfolio database migration chain."""
    path = Path(db_path or PORTFOLIO_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    _upgrade("portfolio_alembic.ini", "portfolio", db_path=path)


__all__ = [
    "run_blog_migrations",
    "run_history_migrations",
    "run_migrations",
    "run_portfolio_migrations",
]
