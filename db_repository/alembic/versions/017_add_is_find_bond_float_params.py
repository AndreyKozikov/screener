"""Add is_find column to bond_float_params.

Revision ID: 017
Revises: 016
Create Date: 2026-02-22

Добавляет столбец is_find: 1 — данные найдены, 0 — данные не найдены.
Значение вносит скрипт пайплайна в зависимости от результата.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет столбец is_find."""
    op.add_column(
        "bond_float_params",
        sa.Column("is_find", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Удаляет столбец is_find."""
    with op.batch_alter_table("bond_float_params", schema=None) as batch_op:
        batch_op.drop_column("is_find")
