"""Add rate column to keyrate if missing.

Revision ID: 004
Revises: 003
Create Date: 2026-02-01

Добавляет колонку rate в таблицу keyrate, если она отсутствует
(например, таблица была создана со старой схемой).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет колонку rate в keyrate, если её нет."""
    conn = op.get_bind()
    # SQLite: проверить наличие колонки через pragma_table_info
    result = conn.execute(sa.text("PRAGMA table_info(keyrate)"))
    columns = [row[1] for row in result.fetchall()]
    if "rate" not in columns:
        op.add_column("keyrate", sa.Column("rate", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    """SQLite не поддерживает DROP COLUMN в старых версиях — откат не меняет схему."""
    pass
