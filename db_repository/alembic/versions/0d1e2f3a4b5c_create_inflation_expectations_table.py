"""create_inflation_expectations_table

Revision ID: 0d1e2f3a4b5c
Revises: f575814afb37
Create Date: 2026-09-13

Создаёт таблицу inflation_expectations для хранения данных по инфляционным
ожиданиям (наблюдаемая и ожидаемая годовая инфляция, 5-летние ожидания,
индекс ожиданий).
Первичный ключ — поле recorddata (date).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d1e2f3a4b5c'
down_revision: Union[str, None] = 'f575814afb37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу inflation_expectations с полем recorddata (PK)
    и полями observed_annual_inflation, expected_annual_inflation,
    expected_five_year_inflation, expectations_index."""
    op.create_table(
        'inflation_expectations',
        sa.Column('recorddata', sa.Date(), nullable=False),
        sa.Column('observed_annual_inflation', sa.Float(), nullable=True),
        sa.Column('expected_annual_inflation', sa.Float(), nullable=True),
        sa.Column('expected_five_year_inflation', sa.Float(), nullable=True),
        sa.Column('expectations_index', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('recorddata'),
    )


def downgrade() -> None:
    """Удаляет таблицу inflation_expectations."""
    op.drop_table('inflation_expectations')
