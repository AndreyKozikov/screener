"""create bonds table

Revision ID: 001
Revises:
Create Date: 2025-01-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bonds",
        sa.Column("secid", sa.String(length=64), nullable=False),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("isin", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("rating", sa.String(length=32), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("coupon_yield_to_price", sa.Float(), nullable=True),
        sa.Column("yield_to_maturity", sa.Float(), nullable=True),
        sa.Column("face_value", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("coupon_value", sa.Float(), nullable=True),
        sa.Column("coupon_percent", sa.Float(), nullable=True),
        sa.Column("coupon_frequency", sa.Float(), nullable=True),
        sa.Column("accrued_interest", sa.Float(), nullable=True),
        sa.Column("duration_years", sa.Float(), nullable=True),
        sa.Column("has_put_option", sa.Integer(), nullable=True),
        sa.Column("has_call_option", sa.Integer(), nullable=True),
        sa.Column("maturity_date", sa.String(length=10), nullable=True),
        sa.Column("listing_level", sa.Integer(), nullable=True),
        sa.Column("bond_type", sa.Integer(), nullable=True),
        sa.Column("bond_kind", sa.Integer(), nullable=True),
        sa.Column("offer_date", sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint("secid"),
    )


def downgrade() -> None:
    op.drop_table("bonds")
