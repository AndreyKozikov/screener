"""Add a role column and promote wisdom's existing account.

Revision ID: 027_add_user_role
Revises: 026_bond_description
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "027_add_user_role"
down_revision: Union[str, None] = "026_bond_description"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.execute(
        sa.text("UPDATE users SET role = 'admin' WHERE lower(email) = :email").bindparams(
            email="nwisdom@yandex.ru"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "role")
