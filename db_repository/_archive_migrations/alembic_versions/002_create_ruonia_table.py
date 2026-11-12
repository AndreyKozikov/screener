"""Create ruonia table.

Revision ID: 002
Revises: (initial)
Create Date: 2026-02-01

Инициализирующая миграция для таблицы ruonia (данные индикатора RUONIA ЦБ РФ).
Первичный ключ — поле dt (date).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу ruonia с полями dt (PK), ruo, vol, T, C, MinRate, Percentile25, Percentile75, MaxRate, StatusXML, DateUpdate."""
    op.create_table(
        "ruonia",
        sa.Column("dt", sa.Date(), nullable=False),
        sa.Column("ruo", sa.Float(), nullable=True),
        sa.Column("vol", sa.Float(), nullable=True),
        sa.Column("T", sa.Float(), nullable=True),
        sa.Column("C", sa.Float(), nullable=True),
        sa.Column("MinRate", sa.Float(), nullable=True),
        sa.Column("Percentile25", sa.Float(), nullable=True),
        sa.Column("Percentile75", sa.Float(), nullable=True),
        sa.Column("MaxRate", sa.Float(), nullable=True),
        sa.Column("StatusXML", sa.Float(), nullable=True),
        sa.Column("DateUpdate", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("dt"),
    )


def downgrade() -> None:
    """Удаляет таблицу ruonia."""
    op.drop_table("ruonia")
