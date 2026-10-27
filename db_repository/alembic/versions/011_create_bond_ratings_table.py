"""Create bond_ratings table.

Revision ID: 011
Revises: 010
Create Date: 2026-02-07

Таблица детальных рейтингов облигаций из bonds_rating.json.
bond_id — FK на bonds.id (ON DELETE CASCADE).
agency_id — FK на rating_agency.agency_id (справочник агентств).
Уникальный индекс (bond_id, agency_id, rating_date) предотвращает дубликаты.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу bond_ratings с FK на bonds и rating_agency."""
    op.create_table(
        "bond_ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agency_id", sa.Integer(), sa.ForeignKey("rating_agency.agency_id"), nullable=False),
        sa.Column("rating_level_name", sa.Text(), nullable=False),
        sa.Column("rating_date", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_bond_ratings_bond_id",
        "bond_ratings",
        ["bond_id"],
        unique=False,
    )
    op.create_index(
        "uq_bond_rating_date",
        "bond_ratings",
        ["bond_id", "agency_id", "rating_date"],
        unique=True,
    )


def downgrade() -> None:
    """Удаляет таблицу bond_ratings."""
    op.drop_index("uq_bond_rating_date", table_name="bond_ratings")
    op.drop_index("idx_bond_ratings_bond_id", table_name="bond_ratings")
    op.drop_table("bond_ratings")
