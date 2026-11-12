"""Merge the user-account and event-detail migration branches.

Revision ID: 023
Revises: 022, 2bd8c788feca, c3d4e5f6a7b8
"""

from typing import Sequence, Union


revision: str = "023"
down_revision: Union[str, Sequence[str], None] = ("022", "2bd8c788feca", "c3d4e5f6a7b8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge point only; both parent branches already apply their changes."""
    pass


def downgrade() -> None:
    """Merge revisions are reversed by explicitly downgrading a parent branch."""
    pass
