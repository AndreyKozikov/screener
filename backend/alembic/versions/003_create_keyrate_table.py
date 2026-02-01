"""Create keyrate table.

Revision ID: 003
Revises: 002
Create Date: 2026-02-01

Инициализирующая миграция для таблицы keyrate (данные ключевой ставки ЦБ РФ).
Первичный ключ — поле dt (date). Поле rate — ключевая ставка, % годовых.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу keyrate с полями dt (PK), rate."""
    op.create_table(
        "keyrate",
        sa.Column("dt", sa.Date(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("dt"),
    )


def downgrade() -> None:
    """Удаляет таблицу keyrate."""
    op.drop_table("keyrate")
