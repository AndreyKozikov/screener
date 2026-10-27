"""Add type column to emitents table.

Revision ID: 012
Revises: 011
Create Date: 2026-02-08

Добавляет колонку type в таблицу emitents для хранения типа ценной бумаги эмитента
(type из API MOEX: ofz_bond, exchange_bond, corporate_bond и др.).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет колонку type в таблицу emitents."""
    op.add_column(
        "emitents",
        sa.Column("type", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Удаляет колонку type из таблицы emitents."""
    op.drop_column("emitents", "type")
