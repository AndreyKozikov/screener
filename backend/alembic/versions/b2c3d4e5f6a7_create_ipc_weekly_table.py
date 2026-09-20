"""create_ipc_weekly_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16

Создаёт таблицу ipc_weekly для хранения недельных индексов потребительских цен.
Первичный ключ — поле start_date (date).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу ipc_weekly с полями start_date (PK), end_date, ipc_weekly, source_url."""
    op.create_table(
        'ipc_weekly',
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('ipc_weekly', sa.Float(), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('start_date'),
    )


def downgrade() -> None:
    """Удаляет таблицу ipc_weekly."""
    op.drop_table('ipc_weekly')
