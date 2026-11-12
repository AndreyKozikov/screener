"""Create emitent_edisclosure mapping table.

Revision ID: 019
Revises: 018
Create Date: 2026-02-28

Таблица для хранения соответствия emitent_id (MOEX, FK на emitents.id)
и edisclosure_id (ID эмитента на e-disclosure.ru).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу emitent_edisclosure с FK на emitents.id и UNIQUE(emitent_id)."""
    op.create_table(
        "emitent_edisclosure",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "emitent_id",
            sa.Integer(),
            sa.ForeignKey("emitents.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("edisclosure_id", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    """Удаляет таблицу emitent_edisclosure."""
    op.drop_table("emitent_edisclosure")
