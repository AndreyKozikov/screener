"""Добавить предупреждение в журнал запусков обновления данных.

Revision ID: 029_data_update_runs_warning
Revises: 028_data_update_runs
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "029_data_update_runs_warning"
down_revision: Union[str, None] = "028_data_update_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_update_runs",
        sa.Column("warning_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("data_update_runs", "warning_message")
