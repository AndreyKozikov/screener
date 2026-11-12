"""add_cascade_to_emitent_ratings_and_bond_emitents

Revision ID: e4b8f31a2c09
Revises: c74a1e9b2f10
Create Date: 2026-08-28 14:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b8f31a2c09'
down_revision: Union[str, None] = 'c74a1e9b2f10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Update bond_emitents with ondelete="CASCADE"
    _tmp_bond_emitents = '_tmp_bond_emitents'
    op.create_table(
        _tmp_bond_emitents,
        sa.Column('secid', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('emitent_id', sa.Integer(), sa.ForeignKey('emitents.id', ondelete='CASCADE'), nullable=False),
    )
    conn.execute(sa.text(f"""
        INSERT INTO {_tmp_bond_emitents} (secid, emitent_id)
        SELECT secid, emitent_id
        FROM bond_emitents
    """))
    op.drop_table('bond_emitents')
    op.rename_table(_tmp_bond_emitents, 'bond_emitents')

    # 2. Update emitent_ratings with ondelete="CASCADE"
    _tmp_emitent_ratings = '_tmp_emitent_ratings'
    op.create_table(
        _tmp_emitent_ratings,
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('emitent_id', sa.Integer(), sa.ForeignKey('emitents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agency_id', sa.Integer(), sa.ForeignKey('rating_agency.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rating_level_name', sa.Text(), nullable=True),
        sa.Column('rating_date', sa.DateTime(), nullable=True),
        sa.Column('rating_publicate_date', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('emitent_id', 'agency_id', name='uq_emitent_ratings_emitent_agency'),
    )
    conn.execute(sa.text(f"""
        INSERT INTO {_tmp_emitent_ratings} (id, emitent_id, agency_id, rating_level_name, rating_date, rating_publicate_date)
        SELECT id, emitent_id, agency_id, rating_level_name, rating_date, rating_publicate_date
        FROM emitent_ratings
    """))
    op.drop_table('emitent_ratings')
    op.rename_table(_tmp_emitent_ratings, 'emitent_ratings')
    op.create_index('idx_emitent_ratings_emitent_id', 'emitent_ratings', ['emitent_id'], unique=False)
    op.create_index('idx_emitent_ratings_agency_id', 'emitent_ratings', ['agency_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    # 1. Revert bond_emitents without ondelete CASCADE
    _tmp_bond_emitents = '_tmp_bond_emitents'
    op.create_table(
        _tmp_bond_emitents,
        sa.Column('secid', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('emitent_id', sa.Integer(), sa.ForeignKey('emitents.id'), nullable=False),
    )
    conn.execute(sa.text(f"""
        INSERT INTO {_tmp_bond_emitents} (secid, emitent_id)
        SELECT secid, emitent_id
        FROM bond_emitents
    """))
    op.drop_table('bond_emitents')
    op.rename_table(_tmp_bond_emitents, 'bond_emitents')

    # 2. Revert emitent_ratings without ondelete CASCADE
    _tmp_emitent_ratings = '_tmp_emitent_ratings'
    op.create_table(
        _tmp_emitent_ratings,
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('emitent_id', sa.Integer(), sa.ForeignKey('emitents.id'), nullable=False),
        sa.Column('agency_id', sa.Integer(), sa.ForeignKey('rating_agency.id'), nullable=False),
        sa.Column('rating_level_name', sa.Text(), nullable=True),
        sa.Column('rating_date', sa.DateTime(), nullable=True),
        sa.Column('rating_publicate_date', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('emitent_id', 'agency_id', name='uq_emitent_ratings_emitent_agency'),
    )
    conn.execute(sa.text(f"""
        INSERT INTO {_tmp_emitent_ratings} (id, emitent_id, agency_id, rating_level_name, rating_date, rating_publicate_date)
        SELECT id, emitent_id, agency_id, rating_level_name, rating_date, rating_publicate_date
        FROM emitent_ratings
    """))
    op.drop_table('emitent_ratings')
    op.rename_table(_tmp_emitent_ratings, 'emitent_ratings')
    op.create_index('idx_emitent_ratings_emitent_id', 'emitent_ratings', ['emitent_id'], unique=False)
    op.create_index('idx_emitent_ratings_agency_id', 'emitent_ratings', ['agency_id'], unique=False)
