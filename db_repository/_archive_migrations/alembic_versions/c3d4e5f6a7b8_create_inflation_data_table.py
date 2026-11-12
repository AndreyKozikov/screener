"""create_inflation_data_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-18

Создаёт таблицу inflation_data для хранения данных об оценках трендовой и базовой инфляции
(трендовая инфляция 3 года, трендовая инфляция 5 лет, модифицированная базовая инфляция).
Первичный ключ — поле record_date (date).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу inflation_data с полем record_date (PK)
    и полями trend_inflation_3y, trend_inflation_5y, modified_core_inflation."""
    op.create_table(
        'inflation_data',
        sa.Column('record_date', sa.Date(), nullable=False),
        sa.Column('trend_inflation_3y', sa.Float(), nullable=True),
        sa.Column('trend_inflation_5y', sa.Float(), nullable=True),
        sa.Column('modified_core_inflation', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('record_date'),
    )


def downgrade() -> None:
    """Удаляет таблицу inflation_data."""
    op.drop_table('inflation_data')
