"""Alembic migration commands owned by the database microservice."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from db_repository.config.paths import BLOG_DB_PATH, DB_PATH, HISTORY_DB_PATH

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


def _upgrade(config_name: str, label: str) -> None:
    config_path = SERVICE_DIR / config_name
    versions = config_path.parent / ("blog_alembic" if config_name == "blog_alembic.ini" else "alembic") / "versions"
    if not config_path.is_file() or not any(versions.glob("*.py")):
        logger.info("No %s migration scripts found; skipping", label)
        return

    result = _run_alembic(config_name, "upgrade", "head")
    if result.returncode == 0:
        logger.info("%s database migrations applied", label)
        return

    output = f"{result.stdout or ''}{result.stderr or ''}"
    lowered = output.lower()
    if "can't locate revision" in lowered or "multiple head revisions" in lowered:
        _run_alembic(config_name, "stamp", "base")
        retry = _run_alembic(config_name, "upgrade", "head")
        if retry.returncode == 0:
            return
        output = f"{retry.stdout or ''}{retry.stderr or ''}"
    elif "already exists" in lowered:
        _run_alembic(config_name, "stamp", "head")
        return

    logger.error("%s database migration failed: %s", label, output)
    raise RuntimeError(f"{label} database migration failed: {output}")


def run_migrations() -> None:
    """Apply the main and history database migration chain."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _upgrade("alembic.ini", "main")


def run_blog_migrations() -> None:
    """Apply the separate blog database migration chain."""
    BLOG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _upgrade("blog_alembic.ini", "blog")


__all__ = ["run_blog_migrations", "run_migrations"]
