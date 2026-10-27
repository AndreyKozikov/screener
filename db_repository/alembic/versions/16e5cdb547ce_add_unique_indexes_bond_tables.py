"""add_unique_indexes_bond_tables

Revision ID: 16e5cdb547ce
Revises: 0a80f75aab87
Create Date: 2026-08-16 15:06:54.822280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16e5cdb547ce'
down_revision: Union[str, None] = '0a80f75aab87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('uq_bondmarketdata_bond_id', 'bondmarketdata', ['bond_id'], unique=True)
    op.create_index('uq_bondmarketdatayield_bond_id', 'bondmarketdatayield', ['bond_id'], unique=True)
    op.create_index('uq_bondsecurity_bond_id', 'bondsecurity', ['bond_id'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_bondsecurity_bond_id', table_name='bondsecurity')
    op.drop_index('uq_bondmarketdatayield_bond_id', table_name='bondmarketdatayield')
    op.drop_index('uq_bondmarketdata_bond_id', table_name='bondmarketdata')

