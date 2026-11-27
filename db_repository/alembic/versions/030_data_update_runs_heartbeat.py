"""Добавить heartbeat в журнал запусков обновления данных.

Revision ID: 030_data_update_runs_heartbeat
Revises: 029_data_update_runs_warning
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "030_data_update_runs_heartbeat"
down_revision: Union[str, None] = "029_data_update_runs_warning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_update_runs",
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        "UPDATE data_update_runs SET heartbeat_at = started_at "
        "WHERE status = 'running'"
    )


def downgrade() -> None:
    op.drop_column("data_update_runs", "heartbeat_at")
