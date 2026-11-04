"""Repair installations stamped at head before the users table was created.

Revision ID: 024
Revises: 023
"""

from typing import Sequence, Union

from alembic import op


revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Earlier migration startup recovery could stamp the database at head after
    # an "already exists" error, leaving this user table unapplied. Keep this
    # repair safe for databases where 022 did create it successfully.
    op.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id VARCHAR(36) NOT NULL PRIMARY KEY, "
        "email VARCHAR(320) NOT NULL, "
        "password_hash VARCHAR(512) NOT NULL, "
        "created_at VARCHAR NOT NULL, "
        "updated_at VARCHAR NOT NULL)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_email")
    op.execute("DROP TABLE IF EXISTS users")
