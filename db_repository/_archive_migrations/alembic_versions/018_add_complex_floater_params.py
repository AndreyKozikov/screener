"""Add complex floater params to bond_float_params.

Revision ID: 018
Revises: 017
Create Date: 2026-02-22

Добавляет поля для сложных финансовых инструментов:
floor_rate, cap_rate, extra_indicators, condition_logic,
observation_type, reference_period_desc.
UNIQUE по bond_id и FK на bonds.id не изменяются.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет столбцы для сложных флоатеров (лимиты ставки, доп. индикаторы, условия)."""
    op.add_column(
        "bond_float_params",
        sa.Column("floor_rate", sa.Float(), nullable=True),
    )
    op.add_column(
        "bond_float_params",
        sa.Column("cap_rate", sa.Float(), nullable=True),
    )
    op.add_column(
        "bond_float_params",
        sa.Column("extra_indicators", sa.Text(), nullable=True),
    )
    op.add_column(
        "bond_float_params",
        sa.Column("condition_logic", sa.Text(), nullable=True),
    )
    op.add_column(
        "bond_float_params",
        sa.Column("observation_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "bond_float_params",
        sa.Column("reference_period_desc", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Удаляет столбцы сложных флоатеров."""
    with op.batch_alter_table("bond_float_params", schema=None) as batch_op:
        batch_op.drop_column("reference_period_desc")
        batch_op.drop_column("observation_type")
        batch_op.drop_column("condition_logic")
        batch_op.drop_column("extra_indicators")
        batch_op.drop_column("cap_rate")
        batch_op.drop_column("floor_rate")
