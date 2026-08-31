"""create_bond_emitents_table

Revision ID: c74a1e9b2f10
Revises: edb174f0fcad
Create Date: 2026-08-27 18:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c74a1e9b2f10'
down_revision: Union[str, None] = 'edb174f0fcad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bond_emitents',
        sa.Column('secid', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('emitent_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['emitent_id'], ['emitents.id']),
        sa.PrimaryKeyConstraint('secid'),
    )


def downgrade() -> None:
    op.drop_table('bond_emitents')
