"""Создать журнал запусков обновления данных.

Revision ID: 028_data_update_runs
Revises: 027_add_user_role
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "028_data_update_runs"
down_revision: Union[str, None] = "027_add_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_update_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_path", sa.String(length=500), nullable=True),
        sa.Column("request_query", sa.Text(), nullable=True),
        sa.Column("log_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_data_update_runs_task_id", "data_update_runs", ["task_id"])
    op.create_index("ix_data_update_runs_status", "data_update_runs", ["status"])
    op.create_index("ix_data_update_runs_started_at", "data_update_runs", ["started_at"])
    op.create_index(
        "ix_data_update_runs_task_started",
        "data_update_runs",
        ["task_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_update_runs_task_started", table_name="data_update_runs")
    op.drop_index("ix_data_update_runs_started_at", table_name="data_update_runs")
    op.drop_index("ix_data_update_runs_status", table_name="data_update_runs")
    op.drop_index("ix_data_update_runs_task_id", table_name="data_update_runs")
    op.drop_table("data_update_runs")
