"""Create rating_agency table.

Revision ID: 006
Revises: d33e65bc9db2
Create Date: 2026-02-07

Справочник рейтинговых агентств. Данные из bonds_rating.json и bonds_emitent.json:
agency_id 0 — Автоматический (ОФЗ); -1 — Нет рейтинга; 3 — АКРА; 4 — Эксперт РА; 5 — НКР; 6 — НРА.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, None] = "d33e65bc9db2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RATING_AGENCY_DATA = [
    {"agency_id": 0, "agency_name_short_ru": "Автоматический", "agency_name_full_ru": "Автоматический (ОФЗ)", "is_system": 1},
    {"agency_id": -1, "agency_name_short_ru": "Нет рейтинга", "agency_name_full_ru": None, "is_system": 1},
    {"agency_id": 3, "agency_name_short_ru": "АКРА", "agency_name_full_ru": "Аналитическое кредитное рейтинговое агентство", "is_system": 0},
    {"agency_id": 4, "agency_name_short_ru": "Эксперт РА", "agency_name_full_ru": "Эксперт РА", "is_system": 0},
    {"agency_id": 5, "agency_name_short_ru": "НКР", "agency_name_full_ru": "Национальное кредитное агентство", "is_system": 0},
    {"agency_id": 6, "agency_name_short_ru": "НРА", "agency_name_full_ru": "Национальное рейтинговое агентство", "is_system": 0},
]


def upgrade() -> None:
    """Создаёт таблицу rating_agency и заполняет справочник данными."""
    op.create_table(
        "rating_agency",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agency_id", sa.Integer(), nullable=False),
        sa.Column("agency_name_short_ru", sa.String(length=64), nullable=False),
        sa.Column("agency_name_full_ru", sa.String(length=256), nullable=True),
        sa.Column("is_system", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_rating_agency_agency_id",
        "rating_agency",
        ["agency_id"],
        unique=True,
    )
    op.create_index(
        "idx_rating_agency_name",
        "rating_agency",
        ["agency_name_short_ru"],
        unique=False,
    )

    rating_agency_table = sa.table(
        "rating_agency",
        sa.column("agency_id", sa.Integer()),
        sa.column("agency_name_short_ru", sa.String(length=64)),
        sa.column("agency_name_full_ru", sa.String(length=256)),
        sa.column("is_system", sa.Integer()),
    )
    op.bulk_insert(rating_agency_table, RATING_AGENCY_DATA)


def downgrade() -> None:
    """Удаляет таблицу rating_agency."""
    op.drop_index("idx_rating_agency_name", table_name="rating_agency")
    op.drop_index("idx_rating_agency_agency_id", table_name="rating_agency")
    op.drop_table("rating_agency")
