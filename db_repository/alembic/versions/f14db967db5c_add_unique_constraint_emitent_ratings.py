"""add_unique_constraint_emitent_ratings

Revision ID: f14db967db5c
Revises: 16e5cdb547ce
Create Date: 2026-08-27 13:41:32.497250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f14db967db5c'
down_revision: Union[str, None] = '16e5cdb547ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_emitent_ratings_emitent_agency',
        'emitent_ratings',
        ['emitent_id', 'agency_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_emitent_ratings_emitent_agency', table_name='emitent_ratings')

