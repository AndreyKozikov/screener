"""Baseline current portfolio database schema

Revision ID: 001_baseline_portfolio_schema
Revises:
Create Date: 2026-11-08

Baseline текущей схемы. Создан по фактическому состоянию базы.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "001_baseline_portfolio_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE portfolios (
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
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_imports (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL UNIQUE REFERENCES portfolios(id) ON DELETE CASCADE,
    parser_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    records_summary_json TEXT,
    error_message TEXT
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_securities (
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
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_trades (
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
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_cash_operations (
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
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_income_payments (
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
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_positions (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id INTEGER NOT NULL REFERENCES portfolio_securities(id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL CHECK (snapshot_type IN ('OPENING', 'CLOSING')),
    quantity INTEGER,
    market_value_ex_nkd_minor INTEGER,
    UNIQUE (portfolio_id, security_id, snapshot_type)
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_security_movements (
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
)"""
    )
    op.execute(
        """CREATE TABLE portfolio_source_rows (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES portfolio_imports(id) ON DELETE CASCADE,
    section_code TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    raw_data_json TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    parse_error TEXT,
    UNIQUE (import_id, section_code, source_row_number)
)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_cash_operation_date ON portfolio_cash_operations(operation_date)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_cash_operation_type ON portfolio_cash_operations(operation_type)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_cash_portfolio_id ON portfolio_cash_operations(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_imports_portfolio_id ON portfolio_imports(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_income_payment_date ON portfolio_income_payments(payment_date)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_income_portfolio_id ON portfolio_income_payments(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_movements_date ON portfolio_security_movements(movement_date)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_movements_portfolio_id ON portfolio_security_movements(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_positions_portfolio_id ON portfolio_positions(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_positions_security_id ON portfolio_positions(security_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_securities_isin ON portfolio_securities(isin)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_securities_portfolio_id ON portfolio_securities(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_source_rows_import_id ON portfolio_source_rows(import_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_trades_portfolio_id ON portfolio_trades(portfolio_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_trades_security_id ON portfolio_trades(security_id)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolio_trades_trade_date ON portfolio_trades(trade_date)"""
    )
    op.execute(
        """CREATE INDEX idx_portfolios_user_id ON portfolios(user_id)"""
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "idx_portfolios_user_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_trades_trade_date"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_trades_security_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_trades_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_source_rows_import_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_securities_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_securities_isin"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_positions_security_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_positions_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_movements_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_movements_date"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_income_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_income_payment_date"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_imports_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_cash_portfolio_id"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_cash_operation_type"')
    op.execute('DROP INDEX IF EXISTS "idx_portfolio_cash_operation_date"')
    op.execute('DROP TABLE IF EXISTS "portfolio_source_rows"')
    op.execute('DROP TABLE IF EXISTS "portfolio_security_movements"')
    op.execute('DROP TABLE IF EXISTS "portfolio_positions"')
    op.execute('DROP TABLE IF EXISTS "portfolio_income_payments"')
    op.execute('DROP TABLE IF EXISTS "portfolio_cash_operations"')
    op.execute('DROP TABLE IF EXISTS "portfolio_trades"')
    op.execute('DROP TABLE IF EXISTS "portfolio_securities"')
    op.execute('DROP TABLE IF EXISTS "portfolio_imports"')
    op.execute('DROP TABLE IF EXISTS "portfolios"')
