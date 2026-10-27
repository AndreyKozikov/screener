"""Drop row_number from emission_documents.

Revision ID: 021
Revises: 020
Create Date: 2026-02-28

Удаление столбца row_number из таблицы emission_documents.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Удаляет столбец row_number из emission_documents."""
    with op.batch_alter_table("emission_documents", schema=None) as batch_op:
        batch_op.drop_column("row_number")


def downgrade() -> None:
    """Восстанавливает столбец row_number в emission_documents."""
    with op.batch_alter_table("emission_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("row_number", sa.Integer(), nullable=True))
