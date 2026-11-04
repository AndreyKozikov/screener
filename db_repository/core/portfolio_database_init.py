"""Schema initialization for the isolated broker portfolio database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from db_repository.config.paths import PORTFOLIO_DB_PATH


PORTFOLIO_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'RUB',
    source_file_name TEXT NOT NULL,
    source_file_sha256 TEXT NOT NULL,
    report_period_start TEXT,
    report_period_end TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, source_file_sha256)
);
CREATE TABLE IF NOT EXISTS portfolio_imports (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL UNIQUE REFERENCES portfolios(id) ON DELETE CASCADE,
    parser_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    records_summary_json TEXT,
    error_message TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_securities (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    isin TEXT,
    security_code TEXT,
    name TEXT NOT NULL,
    currency_code TEXT,
    asset_type TEXT CHECK (asset_type IS NULL OR asset_type IN ('bond', 'non_bond', 'unknown')),
    security_category TEXT,
    issuer TEXT,
    raw_data_json TEXT,
    UNIQUE (portfolio_id, isin)
);
CREATE TABLE IF NOT EXISTS portfolio_trades (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id INTEGER REFERENCES portfolio_securities(id) ON DELETE SET NULL,
    trade_date TEXT NOT NULL,
    settlement_date TEXT,
    trade_time TEXT,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    price_percent_scaled INTEGER,
    amount_ex_nkd_minor INTEGER,
    nkd_minor INTEGER,
    broker_fee_minor INTEGER,
    exchange_fee_minor INTEGER,
    currency_code TEXT,
    trade_number TEXT,
    status TEXT,
    comment TEXT,
    source_row_number INTEGER,
    raw_data_json TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_cash_operations (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id INTEGER REFERENCES portfolio_securities(id) ON DELETE SET NULL,
    trade_id INTEGER REFERENCES portfolio_trades(id) ON DELETE SET NULL,
    operation_date TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK (operation_type IN (
        'COUPON', 'REDEMPTION', 'AMORTIZATION', 'DIVIDEND', 'BROKER_FEE', 'EXCHANGE_FEE',
        'TAX', 'BUY', 'SELL', 'DEPOSIT', 'WITHDRAWAL', 'OTHER'
    )),
    description TEXT,
    amount_minor INTEGER NOT NULL,
    currency_code TEXT,
    source_row_number INTEGER,
    raw_data_json TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_income_payments (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id INTEGER REFERENCES portfolio_securities(id) ON DELETE SET NULL,
    cash_operation_id INTEGER REFERENCES portfolio_cash_operations(id) ON DELETE SET NULL,
    payment_date TEXT NOT NULL,
    income_type TEXT,
    amount_minor INTEGER NOT NULL,
    tax_withheld_minor INTEGER,
    net_amount_minor INTEGER,
    currency_code TEXT,
    description TEXT,
    source_row_number INTEGER,
    raw_data_json TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id INTEGER NOT NULL REFERENCES portfolio_securities(id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL CHECK (snapshot_type IN ('OPENING', 'CLOSING')),
    quantity INTEGER,
    market_value_ex_nkd_minor INTEGER,
    UNIQUE (portfolio_id, security_id, snapshot_type)
);
CREATE TABLE IF NOT EXISTS portfolio_security_movements (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id INTEGER REFERENCES portfolio_securities(id) ON DELETE SET NULL,
    movement_date TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    quantity_delta INTEGER,
    nominal_amount_minor INTEGER,
    currency_code TEXT,
    description TEXT,
    source_row_number INTEGER,
    raw_data_json TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_source_rows (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES portfolio_imports(id) ON DELETE CASCADE,
    section_code TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    raw_data_json TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    parse_error TEXT,
    UNIQUE (import_id, section_code, source_row_number)
);
CREATE INDEX IF NOT EXISTS idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_imports_portfolio_id ON portfolio_imports(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_securities_portfolio_id ON portfolio_securities(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_securities_isin ON portfolio_securities(isin);
CREATE INDEX IF NOT EXISTS idx_portfolio_trades_portfolio_id ON portfolio_trades(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_trades_trade_date ON portfolio_trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_portfolio_trades_security_id ON portfolio_trades(security_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_cash_portfolio_id ON portfolio_cash_operations(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_cash_operation_date ON portfolio_cash_operations(operation_date);
CREATE INDEX IF NOT EXISTS idx_portfolio_cash_operation_type ON portfolio_cash_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_portfolio_income_portfolio_id ON portfolio_income_payments(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_income_payment_date ON portfolio_income_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_portfolio_positions_portfolio_id ON portfolio_positions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_positions_security_id ON portfolio_positions(security_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_movements_portfolio_id ON portfolio_security_movements(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_movements_date ON portfolio_security_movements(movement_date);
CREATE INDEX IF NOT EXISTS idx_portfolio_source_rows_import_id ON portfolio_source_rows(import_id);
"""


def init_portfolio_database(db_path: Path | None = None) -> None:
    """Create the isolated database file and schema when first needed."""
    path = Path(db_path or PORTFOLIO_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(PORTFOLIO_SCHEMA)
        _migrate_portfolio_schema(connection)
        from db_repository.core.portfolio_migration_002 import upgrade

        upgrade(connection)


def _migrate_portfolio_schema(connection: sqlite3.Connection) -> None:
    """Upgrade portfolio tables from scaled quantities to normal integer counts."""
    security_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(portfolio_securities)")
    }
    for column in ("nominal_minor", "nominal_currency_code"):
        if column in security_columns:
            connection.execute(f"ALTER TABLE portfolio_securities DROP COLUMN {column}")

    for table, old_column, new_column in (
        ("portfolio_positions", "quantity_scaled", "quantity"),
        ("portfolio_positions", "planned_quantity_scaled", "planned_quantity"),
        ("portfolio_trades", "quantity_scaled", "quantity"),
        ("portfolio_security_movements", "quantity_delta_scaled", "quantity_delta"),
    ):
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if old_column in columns and new_column not in columns:
            connection.execute(f"ALTER TABLE {table} RENAME COLUMN {old_column} TO {new_column}")
            connection.execute(
                f"UPDATE {table} SET {new_column} = CAST(ROUND({new_column} / 1000000.0) AS INTEGER) "
                f"WHERE {new_column} IS NOT NULL"
            )
    position_columns = {row[1] for row in connection.execute("PRAGMA table_info(portfolio_positions)")}
    if "nominal_minor" in position_columns:
        connection.execute("ALTER TABLE portfolio_positions DROP COLUMN nominal_minor")


__all__ = ["PORTFOLIO_SCHEMA", "init_portfolio_database"]
