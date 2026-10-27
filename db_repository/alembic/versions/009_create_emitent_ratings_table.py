"""Create emitent_ratings table.

Revision ID: 009
Revises: 008
Create Date: 2026-02-07

Таблица рейтингов эмитентов от рейтинговых агентств.
Данные из cci_rating_companies в bonds_emitent.json.
Уникальный индекс (emitent_id, agency_id) для UPSERT.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу emitent_ratings с FK на emitents и rating_agency."""
    op.create_table(
        "emitent_ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("emitent_id", sa.Integer(), sa.ForeignKey("emitents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agency_id", sa.Integer(), sa.ForeignKey("rating_agency.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating_level_name", sa.Text(), nullable=True),
        sa.Column("rating_date", sa.DateTime(), nullable=True),
        sa.Column("rating_publicate_date", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("emitent_id", "agency_id", name="uq_emitent_ratings_emitent_agency"),
    )
    op.create_index(
        "idx_emitent_ratings_emitent_id",
        "emitent_ratings",
        ["emitent_id"],
        unique=False,
    )
    op.create_index(
        "idx_emitent_ratings_agency_id",
        "emitent_ratings",
        ["agency_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет таблицу emitent_ratings."""
    op.drop_index("idx_emitent_ratings_agency_id", table_name="emitent_ratings")
    op.drop_index("idx_emitent_ratings_emitent_id", table_name="emitent_ratings")
    op.drop_table("emitent_ratings")
