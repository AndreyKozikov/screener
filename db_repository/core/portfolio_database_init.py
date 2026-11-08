"""Portfolio database initialization entry point.

The schema is owned by the portfolio Alembic chain. This function only ensures
that the database directory exists and, for a brand-new default database, runs
the baseline migration.
"""

from __future__ import annotations

from pathlib import Path

from db_repository.config.paths import PORTFOLIO_DB_PATH


def init_portfolio_database(db_path: Path | None = None) -> None:
    """Ensure the portfolio database schema exists."""
    path = Path(db_path or PORTFOLIO_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return

    from db_repository.core.migrations import run_portfolio_migrations

    run_portfolio_migrations(path)


__all__ = ["init_portfolio_database"]
