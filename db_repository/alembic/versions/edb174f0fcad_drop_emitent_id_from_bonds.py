"""drop_emitent_id_from_bonds

Revision ID: edb174f0fcad
Revises: f14db967db5c
Create Date: 2026-08-27 18:13:17.208234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'edb174f0fcad'
down_revision: Union[str, None] = 'f14db967db5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bonds", schema=None) as batch_op:
        batch_op.drop_index("ix_bonds_emitent_id")
        batch_op.drop_column("emitent_id")


def downgrade() -> None:
    with op.batch_alter_table("bonds", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "emitent_id",
                sa.Integer(),
                sa.ForeignKey("emitents.id"),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_bonds_emitent_id",
            ["emitent_id"],
            unique=False,
        )
