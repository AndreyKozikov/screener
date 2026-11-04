"""Migration 002: keep only report fields needed for closing portfolio positions."""

from __future__ import annotations

import sqlite3


REVISION = "002_minimal_closing_positions"


def upgrade(connection: sqlite3.Connection) -> None:
    """Remove duplicated market and opening-period fields from snapshots."""
    connection.execute("DELETE FROM portfolio_positions WHERE snapshot_type = 'OPENING'")
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(portfolio_positions)")
    }
    retained = {
        "id",
        "portfolio_id",
        "security_id",
        "snapshot_type",
        "quantity",
        "market_value_ex_nkd_minor",
    }
    for column in sorted(columns - retained):
        connection.execute(f"ALTER TABLE portfolio_positions DROP COLUMN {column}")
