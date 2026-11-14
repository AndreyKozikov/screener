"""Replace bond_emitents with MOEX bond descriptions.

Revision ID: 026_bond_description
Revises: 025_baseline_current_schema
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "026_bond_description"
down_revision: Union[str, None] = "025_baseline_current_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("bond_emitents", "bond_emitents_legacy")
    op.create_table(
        "bond_description",
        sa.Column("bond_id", sa.Integer(), nullable=False),
        sa.Column("issuename", sa.Text(), nullable=True),
        sa.Column("regnumber", sa.String(), nullable=True),
        sa.Column("issuedate", sa.Date(), nullable=True),
        sa.Column("matdate", sa.Date(), nullable=True),
        sa.Column("initialfacevalue", sa.Numeric(15, 2), nullable=True),
        sa.Column("faceunit", sa.String(), nullable=True),
        sa.Column("latname", sa.Text(), nullable=True),
        sa.Column("startdatemoex", sa.Date(), nullable=True),
        sa.Column("hasprospectus", sa.Boolean(), nullable=True),
        sa.Column("decisiondate", sa.Date(), nullable=True),
        sa.Column("isconcessionagreement", sa.Boolean(), nullable=True),
        sa.Column("hasdefault", sa.Boolean(), nullable=True),
        sa.Column("hastechnicaldefault", sa.Boolean(), nullable=True),
        sa.Column("programregistrynumber", sa.String(), nullable=True),
        sa.Column("emitentmismatchcur", sa.Integer(), nullable=True),
        sa.Column("daystoredemption", sa.Integer(), nullable=True),
        sa.Column("issuesize", sa.BigInteger(), nullable=True),
        sa.Column("facevalue", sa.Numeric(15, 2), nullable=True),
        sa.Column("isqualifiedinvestors", sa.Boolean(), nullable=True),
        sa.Column("coupon_benchmark", sa.String(), nullable=True),
        sa.Column("coupon_benchmark_spread", sa.Numeric(10, 4), nullable=True),
        sa.Column("morningsession", sa.Boolean(), nullable=True),
        sa.Column("eveningsession", sa.Boolean(), nullable=True),
        sa.Column("weekendsession", sa.Boolean(), nullable=True),
        sa.Column("registry_date", sa.Date(), nullable=True),
        sa.Column("bond_type", sa.String(), nullable=True),
        sa.Column("bond_subtype", sa.String(), nullable=True),
        sa.Column("facevalue_type", sa.String(), nullable=True),
        sa.Column("coupon_details", sa.String(), nullable=True),
        sa.Column("typename", sa.String(), nullable=True),
        sa.Column("group", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("groupname", sa.String(), nullable=True),
        sa.Column("emitter_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["bond_id"], ["bonds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["emitter_id"], ["emitents.moex_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("bond_id"),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO bond_description (bond_id, emitter_id)
            SELECT b.id, e.moex_id
            FROM bond_emitents_legacy old
            JOIN bonds b ON b.secid = old.secid
            LEFT JOIN emitents e ON e.id = old.emitent_id
            """
        )
    )
    op.drop_table("bond_emitents_legacy")


def downgrade() -> None:
    op.create_table(
        "bond_emitents",
        sa.Column("secid", sa.String(length=64), nullable=False),
        sa.Column("emitent_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["emitent_id"], ["emitents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("secid"),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO bond_emitents (secid, emitent_id)
            SELECT b.secid, MIN(e.id)
            FROM bond_description bd
            JOIN bonds b ON b.id = bd.bond_id
            JOIN emitents e ON e.moex_id = bd.emitter_id
            GROUP BY b.secid
            """
        )
    )
    op.drop_table("bond_description")
