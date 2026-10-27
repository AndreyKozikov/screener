"""Create bond_float_params table.

Revision ID: 016
Revises: 015
Create Date: 2026-02-21

Таблица параметров плавающей ставки облигаций (результат анализа
эмиссионной документации через Gemini). Одна запись на облигацию.
bond_id — FK на bonds.id (ON DELETE CASCADE), UNIQUE.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу bond_float_params с FK на bonds."""
    op.create_table(
        "bond_float_params",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "bond_id",
            sa.Integer(),
            sa.ForeignKey("bonds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # float_params
        sa.Column("base_indicator_code", sa.String(length=64), nullable=False),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("coupon_frequency_days", sa.Integer(), nullable=True),
        sa.Column("lookback_period", sa.Integer(), nullable=True),
        sa.Column("averaging_period", sa.Integer(), nullable=True),
        sa.Column("formula_raw", sa.Text(), nullable=True),
        sa.Column("rate_determination_rule", sa.Text(), nullable=True),
        sa.Column("calculation_type", sa.String(length=32), nullable=True),
        sa.Column("rounding_precision", sa.Integer(), nullable=True),
        sa.Column("key_rate_method", sa.String(length=32), nullable=True),
        sa.Column("lookback_type", sa.String(length=32), nullable=True),
        sa.Column("year_base", sa.String(length=16), nullable=True),
        sa.Column("is_daily_accrual", sa.Boolean(), nullable=False, server_default="0"),
        # calculation_engine
        sa.Column("offset_days", sa.Integer(), nullable=True),
        sa.Column("offset_calendar", sa.String(length=32), nullable=True),
        sa.Column("day_count", sa.String(length=32), nullable=True),
        sa.Column("fallback", sa.String(length=32), nullable=True),
        sa.Column("accrual_type", sa.String(length=32), nullable=True),
        sa.Column(
            "interest_compounding",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        # trading
        sa.Column("placement_date", sa.String(length=10), nullable=True),
        sa.Column("underwriter", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_bond_float_params_bond_id",
        "bond_float_params",
        ["bond_id"],
        unique=True,
    )


def downgrade() -> None:
    """Удаляет таблицу bond_float_params."""
    op.drop_index("uq_bond_float_params_bond_id", table_name="bond_float_params")
    op.drop_table("bond_float_params")
