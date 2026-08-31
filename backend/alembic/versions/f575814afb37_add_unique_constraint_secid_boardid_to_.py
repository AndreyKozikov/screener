"""add_unique_constraint_secid_boardid_to_bonds

Revision ID: f575814afb37
Revises: e4b8f31a2c09
Create Date: 2026-08-30 15:33:33.965153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f575814afb37'
down_revision: Union[str, None] = 'e4b8f31a2c09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('bonds', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_bonds_secid_boardid', ['secid', 'boardid'])


def downgrade() -> None:
    with op.batch_alter_table('bonds', schema=None) as batch_op:
        batch_op.drop_constraint('uq_bonds_secid_boardid', type_='unique')

