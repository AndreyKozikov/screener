"""create_ipc_table

Revision ID: a1b2c3d4e5f6
Revises: 0d1e2f3a4b5c
Create Date: 2026-09-14

Создаёт таблицу ipc_table для хранения индексов потребительских цен
(ИПЦ общий, продовольственные, непродовольственные товары, услуги).
Первичный ключ — поле record_data (date).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0d1e2f3a4b5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу ipc_table с полем record_data (PK)
    и полями ipc, food_ipc, non_food_ipc, services_ipc."""
    op.create_table(
        'ipc_table',
        sa.Column('record_data', sa.Date(), nullable=False),
        sa.Column('ipc', sa.Float(), nullable=True),
        sa.Column('food_ipc', sa.Float(), nullable=True),
        sa.Column('non_food_ipc', sa.Float(), nullable=True),
        sa.Column('services_ipc', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('record_data'),
    )


def downgrade() -> None:
    """Удаляет таблицу ipc_table."""
    op.drop_table('ipc_table')